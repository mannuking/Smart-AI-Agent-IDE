# -*- coding: utf-8 -*-
"""
N8N-Inspired AI Automation Workflow Builder using Streamlit and LangGraph
"""
# Subscribe to the Deep Charts YouTube Channel (https://www.youtube.com/@DeepCharts)

import streamlit as st
import uuid
import os
import re
from typing import List, Dict, Any, Optional, Sequence, TypedDict as TypingTypedDict # Use typing's TypedDict
from datetime import datetime
import json

# --- LangGraph & Tool Imports ---
try:
    from langgraph.graph import StateGraph, START, END
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
    from langchain_core.tools import BaseTool

    LANGGRAPH_AVAILABLE = True
except ImportError as e:
    st.error(
        f"Required libraries not found: {e}. Please install them: \n"
        "`pip install streamlit streamlit-agraph langchain-openai langgraph typing-extensions regex langchain-core`"
    )
    LANGGRAPH_AVAILABLE = False
    # --- DUMMY DEFINITIONS ---
    class BaseMessage: pass
    class HumanMessage(BaseMessage): pass
    class AIMessage(BaseMessage): pass
    class SystemMessage(BaseMessage): pass
    class TypedDict(TypingTypedDict): pass
    def StateGraph(state): return None
    class BaseTool:
        name: str = "dummy_tool"; description: str = "A dummy tool"
        def _run(self, *args: Any, **kwargs: Any) -> Any: pass
        async def _arun(self, *args: Any, **kwargs: Any) -> Any: pass
    START, END = "START", "END"
    # --- END DUMMY DEFINITIONS ---
    st.stop()

# --- Streamlit Agraph Imports ---
try:
    from streamlit_agraph import agraph, Node, Edge, Config
    AGRAPH_AVAILABLE = True
except ImportError:
    st.warning("`streamlit-agraph` not found. Install: `pip install streamlit-agraph`")
    AGRAPH_AVAILABLE = False
    def agraph(*args, **kwargs): pass
    class Node:
        def __init__(self, id, label, **kwargs): self.id = id; self.label = label
    class Edge:
        def __init__(self, source, target, **kwargs): self.source = source; self.target = target
    class Config:
        def __init__(self, **kwargs): pass

# --- Constants ---
ROUTING_KEY_MARKER = "ROUTING_KEY:"
DEFAULT_ROUTING_KEY = "__DEFAULT__"
START_NODE_ID = "__START__"
END_NODE_ID = END

# --- Tool Definition (Using web_search_preview dictionary) ---
web_search_tool_dict = {"type": "web_search_preview"}
tools_list_for_binding = [web_search_tool_dict]

# --- LangGraph State Definition (Dictionary Based) ---
class WorkflowState(TypingTypedDict):
    input: str
    node_outputs: Dict[str, str]
    last_response_content: str
    current_node_id: str

# --- LLM Initialization ---
llm: Optional[ChatOpenAI] = None
llm_with_search: Optional[Any] = None

def initialize_llm() -> bool:
    global llm, llm_with_search
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    openai_ready = bool(openai_api_key)
    if openai_ready and (llm is None or getattr(llm, 'openai_api_key', None) != openai_api_key):
        try:
            base_llm = ChatOpenAI(model_name="gpt-4o", openai_api_key=openai_api_key, temperature=0.2)
            llm = base_llm; llm_with_search = base_llm.bind_tools(tools_list_for_binding)
            print(f"LLM initialized (gpt-4o). Bound: {web_search_tool_dict}")
            return True
        except Exception as e: st.error(f"LLM Init Error: {e}", icon="🔥"); llm = None; llm_with_search = None; return False
    elif not openai_ready:
        if llm is not None: print("Clearing LLM."); llm = None; llm_with_search = None
        return False
    return llm is not None

# --- Helper Function ---
def get_node_display_name(node_id: str) -> str:
    if node_id == START_NODE_ID: return "⏹️ START"
    if node_id == END_NODE_ID: return "🏁 END"
    if "nodes" in st.session_state and isinstance(st.session_state.nodes, list):
        for i, node in enumerate(st.session_state.nodes):
            if isinstance(node, dict) and node.get("id") == node_id: return f"{i+1}. {node.get('name', f'Unk ({node_id})')}"
    return f"Unknown ({node_id})"


# --- Node Execution Function Factory (FIXED CONTENT EXTRACTION) ---
def create_agent_node_function(node_id: str, node_name: str, node_prompt: str, possible_keys: List[str]):
    """ Node function (dict state) with corrected content extraction. """
    def agent_node_function(state: WorkflowState) -> WorkflowState:
        print(f"\n--- Executing Node: {node_name} ({node_id}) ---")
        if "execution_log" not in st.session_state: st.session_state.execution_log = []
        st.session_state.execution_log.append(f"⚙️ Executing Node: **{node_name}**")

        if not llm_with_search: # Error handling for LLM init
            error_msg = f"ERROR: LLM not initialized."; st.session_state.execution_log.append(f"  -> ❌ Error: {error_msg}")
            updated_state = state.copy(); updated_state["last_response_content"] = f"{error_msg} {ROUTING_KEY_MARKER} error"; updated_state["current_node_id"] = node_id; return updated_state

        # --- Prepare Context ---
        context_input = ""; is_first_node = not state.get("last_response_content")
        if is_first_node:
            context_input = state.get("input", ""); print(f"DEBUG: First node, input: '{context_input[:100]}...'")
        else:
            prev_content = state.get("last_response_content", ""); print(f"DEBUG: Prev content type: {type(prev_content)}")
            if isinstance(prev_content, str): context_input = re.sub(rf"\s*{ROUTING_KEY_MARKER}\s*\w+\s*$", "", prev_content).strip()
            else: print("ERROR: Prev content not str"); context_input = str(prev_content) # Fallback
            print(f"DEBUG: Context input: '{context_input[:100]}...'")

        # --- Prepare Prompt ---
        prompt_with_context = node_prompt
        if '{input_text}' in node_prompt: prompt_with_context = node_prompt.replace('{input_text}', context_input)
        elif context_input: prompt_with_context += f"\n\nInput Context:\n{context_input}"
        current_task_prompt = f"Current Task ({node_name}):\n{prompt_with_context}\n(Search web if needed)."
        key_options_text = ", ".join(f"'{k}'" for k in possible_keys if k and k != DEFAULT_ROUTING_KEY)
        routing_instruction = f"\n\n--- ROUTING ---\nAfter response, MUST end with '{ROUTING_KEY_MARKER} <key>' (e.g., from [{key_options_text}]).\n--- END ROUTING ---"
        full_prompt = current_task_prompt + routing_instruction
        print(f"DEBUG: Full prompt type: {type(full_prompt)}"); print(f"Node '{node_name}' sending prompt: {full_prompt[:300]}..."); st.session_state.execution_log.append(f"  📝 Prompt Snippet: {prompt_with_context[:100]}...")

        try:
            # --- Invoke LLM ---
            result = llm_with_search.invoke(full_prompt)
            response_content = "" # Default empty

            # --- *** CORRECTED CONTENT EXTRACTION *** ---
            if hasattr(result, 'content'):
                raw_content = result.content
                if isinstance(raw_content, str):
                    response_content = raw_content # It was already a string
                elif isinstance(raw_content, list) and len(raw_content) > 0 and isinstance(raw_content[0], dict) and 'text' in raw_content[0]:
                    # Standard case for gpt-4o list output: extract text from first block
                    response_content = raw_content[0].get('text', '') # Use .get for safety
                    print("DEBUG: Extracted text from result.content[0]['text']")
                else: # Handle unexpected formats
                    print(f"WARNING: Unexpected format for result.content: {type(raw_content)}. Trying str().")
                    response_content = str(raw_content) # Fallback
            else: print("WARNING: result has no 'content' attribute.")
            # --- *** END CORRECTION *** ---

            # --- Debugging & Logging ---
            print(f"\nDEBUG: Raw result type: {type(result)}")
            # print(f"DEBUG: Raw result value: {result}") # Can be very verbose
            print(f"DEBUG: response_content type: {type(response_content)}") # Should be str now
            print(f"DEBUG: response_content value: '{str(response_content)[:500]}...'")
            log_snippet = str(response_content)[:100] if response_content is not None else "[No text content]"
            st.session_state.execution_log.append(f"  🤖 LLM Response Snippet: {log_snippet}...")

            # --- Tool Call Warning (if they still appear) ---
            if hasattr(result, 'tool_calls') and result.tool_calls:
                 calls = result.tool_calls; call_details = [f"{call.get('name', '?')}({call.get('args', {})})" for call in calls]
                 warning_msg = f"  ⚠️ WARNING: LLM response included 'tool_calls' ({call_details}). Graph not handling them."; print(warning_msg); st.session_state.execution_log.append(warning_msg); st.warning(warning_msg)

            # --- Routing Key Check (Should work on extracted string now) ---
            if isinstance(response_content, str):
                match = re.search(rf"{ROUTING_KEY_MARKER}\s*(\w+)\s*$", response_content)
                if match: st.session_state.execution_log.append(f"  🔑 Detected key: '{match.group(1)}'.")
                else: st.session_state.execution_log.append(f"  ⚠️ WARNING: No routing key found."); response_content += f" {ROUTING_KEY_MARKER} {DEFAULT_ROUTING_KEY}"; st.session_state.execution_log.append(f"  🔧 Appended default key.")
            else: # Should not happen now, but keep as safeguard
                 st.session_state.execution_log.append(f"  ⚠️ ERROR: Extracted content not str ({type(response_content)}).")
                 response_content = f"Error: Invalid type {ROUTING_KEY_MARKER} {DEFAULT_ROUTING_KEY}"

            # --- Update State ---
            updated_state = state.copy()
            if "node_outputs" not in updated_state or not isinstance(updated_state["node_outputs"], dict): updated_state["node_outputs"] = {}
            updated_state["node_outputs"][node_id] = str(response_content) # Store string
            updated_state["last_response_content"] = str(response_content) # Store string
            updated_state["current_node_id"] = node_id
            return updated_state

        # --- Exception Handling ---
        except Exception as e: # Catch any other errors during invoke/processing
            error_msg = f"Error in node {node_name} ({node_id}): {e}"
            print(error_msg); st.session_state.execution_log.append(f"  -> ❌ Error: {e}")
            updated_state = state.copy(); updated_state["last_response_content"] = f"ERROR: {error_msg} {ROUTING_KEY_MARKER} error"; updated_state["current_node_id"] = node_id
            import traceback; traceback.print_exc(); return updated_state

    return agent_node_function


# --- Generic Router Function (Dictionary State Version - CORRECTED FORMATTING) ---
def generic_router(state: WorkflowState) -> str:
    """ Determines route based on key in state['last_response_content']. """
    print("\n--- Routing Check ---")
    routing_key = DEFAULT_ROUTING_KEY # Default if no key found
    last_content = state.get("last_response_content", "")

    if last_content:
        # Ensure last_content is treated as a string
        if isinstance(last_content, str):
             match = re.search(rf"{ROUTING_KEY_MARKER}\s*(\w+)\s*$", last_content)
             if match:
                 # Key found, use it
                 routing_key = match.group(1).strip()
                 print(f"  Extracted key: '{routing_key}'")
             else:
                 # String content, but no key found at the end
                 print(f"  No routing key found in last response: '...{last_content[-50:]}'")
                 print(f"  -> Using default routing ('{DEFAULT_ROUTING_KEY}').")
        else:
             # Content is not a string (shouldn't happen often with current node logic, but good practice)
             print(f"  Last response content type is {type(last_content)}, not string.")
             print(f"  -> Using default routing ('{DEFAULT_ROUTING_KEY}').")
    else:
        # No previous response content found in state
        print(f"  No previous response content found.")
        print(f"  -> Using default routing ('{DEFAULT_ROUTING_KEY}').")

    # Log and return the determined routing key
    log_decision_msg = f"🚦 Routing decision: '{routing_key}'"
    print(f"  -> {log_decision_msg}")
    if "execution_log" not in st.session_state: st.session_state.execution_log = []
    st.session_state.execution_log.append(log_decision_msg)
    return routing_key

# --- Graph Compilation Function (Dictionary State Version - No Change) ---
def compile_graph() -> bool:
    if not llm: st.error("LLM not initialized.", icon="🔥"); return False
    if not st.session_state.nodes: st.warning("No nodes defined.", icon="⚠️"); return False
    print("\n--- Compiling Graph (Dictionary State) ---")
    try:
        graph_builder = StateGraph(WorkflowState); valid_nodes = [n for n in st.session_state.nodes if isinstance(n, dict) and all(k in n for k in ["id", "name", "prompt"])];
        if not valid_nodes: st.warning("No valid nodes.", icon="⚠️"); return False
        node_ids = {node['id'] for node in valid_nodes}; start_node_id_actual = valid_nodes[0]["id"]; print("  Adding Nodes:")
        possible_keys_per_node = {}
        for node_data in valid_nodes:
            node_id, node_name, node_prompt = node_data["id"], node_data["name"], node_data["prompt"]; print(f"    - ID: {node_id}, Name: '{node_name}'")
            routing_rules = node_data.get("routing_rules", {}); cond_keys = {rule.get("output_key", "").strip() for rule in routing_rules.get("conditional_targets", []) if rule.get("output_key")}
            all_keys = cond_keys.union({DEFAULT_ROUTING_KEY, "error"}); possible_keys_per_node[node_id] = list(all_keys); agent_func = create_agent_node_function(node_id, node_name, node_prompt, possible_keys_per_node[node_id])
            graph_builder.add_node(node_id, agent_func)
        print("  Adding Edges:"); graph_builder.add_edge(START, start_node_id_actual); print(f"    - START -> {get_node_display_name(start_node_id_actual)}")
        all_targets_valid = True
        for node_data in valid_nodes:
            node_id, node_name = node_data["id"], node_data["name"]; routing_rules = node_data.get("routing_rules", {}); default_target = routing_rules.get("default_target", END_NODE_ID); conditional_targets = routing_rules.get("conditional_targets", [])
            path_map = {}; print(f"    - Edges from '{node_name}' ({node_id}):"); seen_keys_for_node = set(); node_targets_valid = True
            for rule_idx, rule in enumerate(conditional_targets):
                key, target_id = rule.get("output_key", "").strip(), rule.get("target_node_id")
                if key and target_id:
                    if target_id != END_NODE_ID and target_id not in node_ids: st.error(f"❌ Invalid Target: {node_name} '{key}'->'{get_node_display_name(target_id)}'", icon="🔥"); all_targets_valid=False; node_targets_valid=False; continue
                    if key in seen_keys_for_node: st.warning(f"⚠️ Duplicate key '{key}' in '{node_name}'.", icon="⚠️")
                    path_map[key] = target_id; seen_keys_for_node.add(key); print(f"      - If key '{key}' -> {get_node_display_name(target_id)}")
                elif key or target_id: st.warning(f"Node '{node_name}' incomplete rule #{rule_idx+1}. Ignored.", icon="⚠️")
            if DEFAULT_ROUTING_KEY not in path_map:
                 if default_target != END_NODE_ID and default_target not in node_ids: st.error(f"❌ Invalid Default Target: {node_name}->'{get_node_display_name(default_target)}'", icon="🔥"); all_targets_valid=False; node_targets_valid=False
                 else: path_map[DEFAULT_ROUTING_KEY] = default_target; print(f"      - If key '{DEFAULT_ROUTING_KEY}' -> {get_node_display_name(default_target)}")
            if "error" not in path_map: path_map["error"] = END_NODE_ID; print(f"      - If key 'error' -> {get_node_display_name(END_NODE_ID)} (Implicit)")
            if node_targets_valid: graph_builder.add_conditional_edges(node_id, generic_router, path_map)
            else: print(f"      -> Skipping edges for '{node_name}'.")
        if not all_targets_valid: st.error("Compilation failed.", icon="🔥"); return False
        recursion_limit = len(valid_nodes) * 3 + 10; print(f"  Setting recursion limit to: {recursion_limit}")
        st.session_state.compiled_graph = graph_builder.compile(checkpointer=None); st.session_state.recursion_limit = recursion_limit
        print("✅ Graph compiled successfully!"); st.toast("Workflow compiled!", icon="✅"); return True
    except Exception as e: st.error(f"Compile error: {e}", icon="🔥"); print(f"❌ Compile Error: {e}"); import traceback; traceback.print_exc(); st.session_state.compiled_graph = None; return False

# --- Graph Visualization Data Generation (No Change) ---
def generate_agraph_data(nodes_data: List[Dict[str, Any]]) -> tuple[List[Node], List[Edge]]:
    agraph_nodes: List[Node] = []; agraph_edges: List[Edge] = []
    agraph_nodes.append(Node(id=START_NODE_ID, label="START", shape="ellipse", color="#4CAF50", title="Workflow Entry Point"))
    valid_nodes_vis = [node for node in nodes_data if isinstance(node, dict) and 'id' in node]
    node_ids_vis = {node['id'] for node in valid_nodes_vis}; node_indices = {node['id']: i for i, node in enumerate(valid_nodes_vis)}
    for i, node in enumerate(valid_nodes_vis):
        node_id = node['id']; node_name = node.get('name', 'Unnamed'); node_prompt_snippet = node.get('prompt', '')[:100] + "..."
        is_selected = st.session_state.get('selected_node_id') == node_id; border_width = 3 if is_selected else 1; node_color = "#FFC107" if is_selected else "#90CAF9"
        agraph_nodes.append(Node(id=node_id, label=f"{i+1}. {node_name}", shape="box", color=node_color, borderWidth=border_width, title=f"ID: {node_id}\nPrompt: {node_prompt_snippet}"))
        if i == 0: agraph_edges.append(Edge(source=START_NODE_ID, target=node_id, label="Start Flow", color="#4CAF50", width=2))
        routing_rules = node.get("routing_rules", {}); default_target = routing_rules.get("default_target", END_NODE_ID); conditional_targets = routing_rules.get("conditional_targets", [])
        added_vis_edges = set()
        if default_target == END_NODE_ID or default_target in node_ids_vis:
            is_overridden = any(r.get("output_key") == DEFAULT_ROUTING_KEY for r in conditional_targets); edge_id = (node_id, default_target, DEFAULT_ROUTING_KEY)
            if not is_overridden and edge_id not in added_vis_edges: agraph_edges.append(Edge(source=node_id, target=default_target, label=DEFAULT_ROUTING_KEY, color="#9E9E9E", dashes=True, arrows="to", font={'align': 'middle'})); added_vis_edges.add(edge_id)
        for rule in conditional_targets:
            key, target_id = rule.get("output_key", "").strip(), rule.get("target_node_id")
            if key and target_id and (target_id == END_NODE_ID or target_id in node_ids_vis):
                edge_id = (node_id, target_id, key)
                if edge_id not in added_vis_edges:
                    is_loopback = False
                    if target_id in node_indices and node_id in node_indices:
                         if node_indices[target_id] < node_indices[node_id]: is_loopback = True
                    edge_color = "#FF5722" if is_loopback else "#2196F3"; edge_label = f"LOOP: {key}" if is_loopback else key
                    agraph_edges.append(Edge(source=node_id, target=target_id, label=edge_label, color=edge_color, arrows="to", font={'align': 'middle'})); added_vis_edges.add(edge_id)
    if any(hasattr(edge, 'target') and edge.target == END_NODE_ID for edge in agraph_edges):
        agraph_nodes.append(Node(id=END_NODE_ID, label="END", shape="ellipse", color="#F44336", title="Workflow End"))
    return agraph_nodes, agraph_edges

# --- Example Workflow Definitions (No Change) ---
def get_simple_summarizer_workflow(): node_id = f"summarize_node_{uuid.uuid4().hex[:4]}"; return [ { "id": node_id, "name": "Summarize Input", "prompt": f"Summarize the input text concisely (1-2 sentences).", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]} } ]
def get_sentiment_workflow(): ids = {name: f"sentiment_node_{uuid.uuid4().hex[:4]}" for name in ["analyzer", "positive", "negative", "neutral"]}; nodes = [ { "id": ids["analyzer"], "name": "Analyze Sentiment", "prompt": f"Analyze sentiment (Positive, Negative, Neutral) of the input. Respond ONLY with the result.", "type": "llm_call", "routing_rules": { "default_target": ids["neutral"], "conditional_targets": [ {"output_key": "Positive", "target_node_id": ids["positive"]}, {"output_key": "Negative", "target_node_id": ids["negative"]}, {"output_key": "Neutral", "target_node_id": ids["neutral"]} ]}}, { "id": ids["positive"], "name": "Handle Positive", "prompt": f"Sentiment was positive. Respond cheerfully.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]}}, { "id": ids["negative"], "name": "Handle Negative", "prompt": f"Sentiment was negative. Respond empathetically.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]}}, { "id": ids["neutral"], "name": "Handle Neutral", "prompt": f"Sentiment was neutral. Acknowledge receipt.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]}} ]; return nodes
def get_classification_workflow(): ids = {name: f"classify_node_{uuid.uuid4().hex[:4]}" for name in ["classify", "complaint", "query", "compliment", "general"]}; nodes = [ { "id": ids["classify"], "name": "Extract & Classify Intent", "prompt": f"From input, extract product/person (or 'None'). Classify intent: Complaint, Query, Compliment. Respond STRICTLY:\nExtracted Info: [Info]\nIntent: [IntentWord]", "type": "llm_call", "routing_rules": { "default_target": ids["general"], "conditional_targets": [ {"output_key": "Complaint", "target_node_id": ids["complaint"]}, {"output_key": "Query", "target_node_id": ids["query"]}, {"output_key": "Compliment", "target_node_id": ids["compliment"]} ]}}, { "id": ids["complaint"], "name": "Handle Complaint", "prompt": f"Complaint received. Respond empathetically, use extracted info.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]}}, { "id": ids["query"], "name": "Answer Query", "prompt": f"Query received. Answer based on context/info. Use web search if needed.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]}}, { "id": ids["compliment"], "name": "Handle Compliment", "prompt": f"Compliment received. Respond thankfully.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]}}, { "id": ids["general"], "name": "General Response", "prompt": f"Intent unclear. Provide generic response.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"done", "target_node_id": END_NODE_ID}]}} ]; return nodes
def get_deep_research_workflow(): ids = {name: f"dr_node_{uuid.uuid4().hex[:4]}" for name in [ "planner", "search_A", "search_B", "cross_reference", "synthesize", "final_report" ]}; nodes = [ { "id": ids["planner"], "name": "📝 Research Planner", "prompt": f"Analyze the research goal. Break into 1-3 angles (A, B). State plan. Decide if single/multi angle needed.", "type": "llm_call", "routing_rules": { "default_target": ids["search_A"], "conditional_targets": [ {"output_key": "single_angle", "target_node_id": ids["search_A"]}, {"output_key": "multi_angle", "target_node_id": ids["search_A"]} ] } }, { "id": ids["search_A"], "name": "🔍 Research Angle A", "prompt": f"Research Angle A based on plan. Use web search if necessary. Summarize findings for Angle A.", "type": "llm_call", "routing_rules": { "default_target": ids["search_B"], "conditional_targets": [ {"output_key": "synthesize_direct", "target_node_id": ids["synthesize"]}, {"output_key": "next_angle", "target_node_id": ids["search_B"]} ] } }, { "id": ids["search_B"], "name": "🔎 Research Angle B", "prompt": f"Research Angle B based on plan. Use web search if necessary. Summarize findings for Angle B.", "type": "llm_call", "routing_rules": { "default_target": ids["cross_reference"], "conditional_targets": [ {"output_key": "cross_reference", "target_node_id": ids["cross_reference"]} ] } }, { "id": ids["cross_reference"], "name": "🔄 Cross-Reference & Validate", "prompt": f"Review findings from Angle A & B. Identify agreements/contradictions/gaps. Use web search to verify if needed.", "type": "llm_call", "routing_rules": { "default_target": ids["synthesize"], "conditional_targets": [ {"output_key": "revisit_A", "target_node_id": ids["search_A"]}, {"output_key": "revisit_B", "target_node_id": ids["search_B"]}, {"output_key": "synthesize", "target_node_id": ids["synthesize"]} ] } }, { "id": ids["synthesize"], "name": "🧩 Synthesize Findings", "prompt": f"Combine validated findings from research angles. Create concise summary for original goal.", "type": "llm_call", "routing_rules": { "default_target": ids["final_report"], "conditional_targets": [ {"output_key": "refine_synthesis", "target_node_id": ids["cross_reference"]}, {"output_key": "final_report", "target_node_id": ids["final_report"]} ] } }, { "id": ids["final_report"], "name": "📄 Generate Final Report", "prompt": f"Format synthesized findings into clear final report.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key": "done", "target_node_id": END_NODE_ID}]} } ]; return nodes
def get_enhanced_hedge_fund_workflow(): ids = {name: f"ehf_node_{uuid.uuid4().hex[:4]}" for name in [ "goal_risk", "planner", "macro", "sector", "company", "risk_assess", "strategist" ]}; nodes = [ { "id": ids["goal_risk"], "name": "🎯 Goal & Risk Profiler", "prompt": f"Analyze investment goal from input. Clarify timeframe, expectations, infer risk tolerance (Conservative, Balanced, Aggressive). State profile.", "type": "llm_call", "routing_rules": { "default_target": ids["planner"], "conditional_targets": [ {"output_key": "plan_research", "target_node_id": ids["planner"]} ] } }, { "id": ids["planner"], "name": "🗺️ Advanced Research Planner", "prompt": f"Based on Goal/Risk, determine necessary research steps & sequence (Macro, Sector, Company). State plan. Decide FIRST step.", "type": "llm_call", "routing_rules": { "default_target": ids["risk_assess"], "conditional_targets": [ {"output_key": "research_macro", "target_node_id": ids["macro"]}, {"output_key": "research_sector", "target_node_id": ids["sector"]}, {"output_key": "research_company", "target_node_id": ids["company"]}, {"output_key": "go_strategy", "target_node_id": ids["strategist"]} ] } }, { "id": ids["macro"], "name": "📈 Macro Researcher", "prompt": f"Perform macro analysis relevant to Goal/Risk. Use web search if needed (GDP, rates, inflation). Summarize findings & impacts. Determine NEXT planned step.", "type": "llm_call", "routing_rules": { "default_target": ids["risk_assess"], "conditional_targets": [ {"output_key": "research_sector", "target_node_id": ids["sector"]}, {"output_key": "research_company", "target_node_id": ids["company"]}, {"output_key": "assess_risk", "target_node_id": ids["risk_assess"]} ] } }, { "id": ids["sector"], "name": "🏭 Sector Researcher", "prompt": f"Perform sector analysis relevant to Goal/Risk (guided by macro). Use web search if needed (trends/competitors). Summarize findings & impacts. Determine NEXT planned step.", "type": "llm_call", "routing_rules": { "default_target": ids["risk_assess"], "conditional_targets": [ {"output_key": "research_macro", "target_node_id": ids["macro"]}, {"output_key": "research_company", "target_node_id": ids["company"]}, {"output_key": "assess_risk", "target_node_id": ids["risk_assess"]} ] } }, { "id": ids["company"], "name": "🏢 Company Researcher", "prompt": f"Perform company analysis relevant to Goal/Risk (guided by macro/sector). Use web search if needed (news, financials). Summarize findings (valuation, risks) & impacts. Determine NEXT planned step.", "type": "llm_call", "routing_rules": { "default_target": ids["risk_assess"], "conditional_targets": [ {"output_key": "research_macro", "target_node_id": ids["macro"]}, {"output_key": "research_sector", "target_node_id": ids["sector"]}, {"output_key": "assess_risk", "target_node_id": ids["risk_assess"]} ] } }, { "id": ids["risk_assess"], "name": "⚠️ Risk Assessor & Validator", "prompt": f"Review ALL research findings against Goal/Risk. Identify key risks, inconsistencies, gaps. Use web search to verify if needed.", "type": "llm_call", "routing_rules": { "default_target": ids["strategist"], "conditional_targets": [ {"output_key": "revisit_macro", "target_node_id": ids["macro"]}, {"output_key": "revisit_sector", "target_node_id": ids["sector"]}, {"output_key": "revisit_company", "target_node_id": ids["company"]}, {"output_key": "create_strategy", "target_node_id": ids["strategist"]} ] } }, { "id": ids["strategist"], "name": "💰 Portfolio Strategist", "prompt": f"Synthesize validated research. Develop specific, diversified portfolio allocation strategy tailored to Goal/Risk. Justify strategy.", "type": "llm_call", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": [{"output_key":"portfolio_ready", "target_node_id": END_NODE_ID}]} } ]; return nodes

# --- Helper Function to Load Workflow (No Change) ---
def load_workflow(workflow_func):
     try: st.session_state.nodes = workflow_func(); st.session_state.compiled_graph = None; st.session_state.selected_node_id = st.session_state.nodes[0]['id'] if st.session_state.nodes else None; st.session_state.execution_log = []; st.session_state.final_state = None; st.session_state.recursion_limit = None; wf_name = workflow_func.__name__.replace('get_','').replace('_workflow','').replace('_', ' ').title(); st.toast(f"{wf_name} loaded!", icon="📄"); st.rerun()
     except Exception as e: st.error(f"Load Error: {e}"); print(f"Load Error: {e}"); import traceback; traceback.print_exc()

# --- Session State Initialization (WITH SYNTAX FIX) ---
default_values = { "compiled_graph": None, "execution_log": [], "final_state": None, "selected_node_id": None, "recursion_limit": None, "openai_api_key_provided": False }
for key, value in default_values.items(): st.session_state.setdefault(key, value)
if "nodes" not in st.session_state or not st.session_state.nodes:
    try:
        print("Loading default workflow"); st.session_state.nodes = get_enhanced_hedge_fund_workflow()
        if st.session_state.nodes and isinstance(st.session_state.nodes, list): st.session_state.selected_node_id = st.session_state.nodes[0].get('id')
    except Exception as e: # Corrected Block
        print(f"Default load error: {e}"); st.session_state.nodes = []
    # --- END CORRECTION ---

# --- Helper UI Functions (Readable Versions with Syntax Fix) ---
def get_node_options_for_select(include_end=True, exclude_node_id: Optional[str] = None) -> List[tuple[str, str]]:
    options = []; node_list = st.session_state.get("nodes", [])
    if isinstance(node_list, list):
        options.extend([(node.get("id"), f"{i+1}. {node.get('name', 'Unnamed')}") for i, node in enumerate(node_list) if isinstance(node, dict) and node.get("id") != exclude_node_id])
    if include_end and END_NODE_ID != exclude_node_id: options.append((END_NODE_ID, get_node_display_name(END_NODE_ID)))
    return options
def select_node(node_id: Optional[str]): st.session_state.selected_node_id = node_id
def update_node_data_ui(node_id: str, data: Dict[str, Any]):
    updated = False; node_list = st.session_state.get("nodes", [])
    if isinstance(node_list, list):
        for i, node in enumerate(node_list):
            if isinstance(node, dict) and node.get("id") == node_id:
                try: new_rules = json.loads(json.dumps(data.get("routing_rules", {})))
                except Exception: st.error("Serialize Error."); return
                node["name"] = data.get("name", node.get("name")); node["prompt"] = data.get("prompt", node.get("prompt")); node["routing_rules"] = new_rules; updated = True; break
    if updated: st.session_state.compiled_graph = None; st.toast(f"Node '{data.get('name', node_id)}' updated.", icon="💾"); st.session_state.selected_node_id = node_id
    else: st.error(f"Node {node_id} not found.")
def delete_node_ui(node_id_to_delete: str):
    node_list = st.session_state.get("nodes", [])
    if isinstance(node_list, list):
        original_len = len(node_list); node_name_deleted = get_node_display_name(node_id_to_delete)
        st.session_state.nodes = [n for n in node_list if not (isinstance(n, dict) and n.get("id") == node_id_to_delete)]
        if len(st.session_state.nodes) < original_len:
            st.session_state.compiled_graph = None
            if st.session_state.selected_node_id == node_id_to_delete: st.session_state.selected_node_id = st.session_state.nodes[0]['id'] if st.session_state.nodes else None
            st.toast(f"Deleted {node_name_deleted}", icon="🗑️"); st.rerun()
        else: st.warning(f"Node {node_id_to_delete} not found.")
def move_node_ui(node_id_to_move: str, direction: int): # Readable Version with Syntax Fix
    node_list = st.session_state.get("nodes", [])
    if isinstance(node_list, list):
        try:
            index = next(i for i, n in enumerate(node_list) if isinstance(n, dict) and n.get("id") == node_id_to_move)
            new_index = index + direction
            if 0 <= new_index < len(node_list):
                node = node_list.pop(index)
                node_list.insert(new_index, node)
                st.session_state.compiled_graph = None
                st.session_state.selected_node_id = node_id_to_move
                st.rerun()
        except StopIteration: # Correctly placed except block
            st.warning(f"Node {node_id_to_move} not found for moving.")
def add_conditional_rule_ui(node_id: str):
    node_list = st.session_state.get("nodes", [])
    if isinstance(node_list, list):
        for i, node in enumerate(node_list):
            if isinstance(node, dict) and node.get("id") == node_id:
                if not isinstance(node.get("routing_rules"), dict): node["routing_rules"] = {}
                if not isinstance(node["routing_rules"].get("conditional_targets"), list): node["routing_rules"]["conditional_targets"] = []
                node["routing_rules"]["conditional_targets"].append({"output_key": "", "target_node_id": END_NODE_ID}); st.session_state.compiled_graph = None; st.session_state.selected_node_id = node_id; st.rerun(); return
    st.error(f"Node {node_id} not found.")
def delete_conditional_rule_ui(node_id: str, rule_index: int):
    node_list = st.session_state.get("nodes", [])
    if isinstance(node_list, list):
         for i, node in enumerate(node_list):
             if isinstance(node, dict) and node.get("id") == node_id:
                 rules_list = node.get("routing_rules", {}).get("conditional_targets")
                 if isinstance(rules_list, list) and 0 <= rule_index < len(rules_list):
                     del node["routing_rules"]["conditional_targets"][rule_index]; st.session_state.compiled_graph = None; st.session_state.selected_node_id = node_id; st.rerun(); return
                 else: st.warning(f"Invalid rule index {rule_index}."); return
         st.error(f"Node {node_id} not found.")

# --- Streamlit App UI (No Change) ---
st.set_page_config(layout="wide", page_title="Visual AI Automation Builder ", page_icon="🤖")
st.title("🤖🧠 Visual AI Automation Builder")
now = datetime.now(); current_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"Uses Dictionary State. LLM: `gpt-4o` (bound: `{web_search_tool_dict}`). Refresh: {current_timestamp}")
with st.sidebar: # Sidebar UI (No Change)
    st.header("🔑 OpenAI API Key"); openai_api_key_input = st.text_input("API Key", type="password", value=os.environ.get("OPENAI_API_KEY", ""), help="Needed for LLM nodes.", key="api_key_input_sidebar"); api_key_in_env = os.environ.get("OPENAI_API_KEY"); api_key_changed = (openai_api_key_input != api_key_in_env if api_key_in_env else bool(openai_api_key_input))
    if api_key_changed:
        if openai_api_key_input: os.environ["OPENAI_API_KEY"] = openai_api_key_input
        elif "OPENAI_API_KEY" in os.environ: del os.environ["OPENAI_API_KEY"]
        llm = None; llm_with_search = None; llm_ready = initialize_llm(); st.session_state.openai_api_key_provided = bool(openai_api_key_input)
        if api_key_changed: st.session_state.compiled_graph = None; st.rerun()
    else: llm_ready = initialize_llm(); st.session_state.openai_api_key_provided = bool(os.environ.get("OPENAI_API_KEY"))
    if llm_ready: st.success("LLM Initialized.", icon="✅")
    elif st.session_state.get("openai_api_key_provided"): st.error("LLM Init Failed.", icon="🔥")
    else: st.warning("LLM needs API Key.", icon="⚠️")
    st.caption(f"Tool binding: `{web_search_tool_dict}`"); st.divider()
    st.header("🧩 Node Palette");
    with st.form("add_node_form"):
        new_node_name_input = st.text_input("New Node Name", placeholder="e.g., 'Summarize Input'", key="new_node_name_palette_main"); add_node_submitted = st.form_submit_button("➕ Add LLM Node", use_container_width=True)
        if add_node_submitted:
            if new_node_name_input:
                if any(isinstance(n, dict) and n.get('name') == new_node_name_input for n in st.session_state.nodes): st.warning(f"Name exists.", icon="⚠️")
                else: node_id = f"node_{uuid.uuid4().hex[:6]}"; st.session_state.nodes.append({"id": node_id, "name": new_node_name_input, "type": "llm_call", "prompt": f"Task: {new_node_name_input}\nInput: {{input_text}}\n(Use web search if needed.)", "routing_rules": {"default_target": END_NODE_ID, "conditional_targets": []}}); st.session_state.compiled_graph = None; st.session_state.selected_node_id = node_id; st.toast(f"Added: {new_node_name_input}", icon="➕"); st.rerun()
            else: st.error("Node Name required.", icon="❗")
    st.divider(); st.header("📜 Example Workflows"); ex_cols = st.columns(2)
    with ex_cols[0]: st.button("📄 Summarizer", use_container_width=True, key="load_summarizer_btn", on_click=load_workflow, args=(get_simple_summarizer_workflow,)); st.button("🎭 Sentiment", use_container_width=True, key="load_sentiment_btn", on_click=load_workflow, args=(get_sentiment_workflow,)); st.button("🔬 Deep Research", use_container_width=True, key="load_deep_research_btn", on_click=load_workflow, args=(get_deep_research_workflow,))
    with ex_cols[1]: st.button("🏷️ Classify", use_container_width=True, key="load_classify_btn", on_click=load_workflow, args=(get_classification_workflow,)); st.button("📈 Adv. Hedge Fund", use_container_width=True, key="load_adv_hedge_btn", on_click=load_workflow, args=(get_enhanced_hedge_fund_workflow,))
    st.divider(); st.header("⚙️ Workflow Control"); compile_disabled = not llm_ready or not st.session_state.nodes; tooltip_compile = "Requires API Key & nodes." if compile_disabled else "Compile workflow.";
    if st.button("🔄 Compile Workflow", type="primary", use_container_width=True, disabled=compile_disabled, help=tooltip_compile, key="compile_workflow_btn"):
        if compile_graph(): st.rerun()
    tooltip_reset = "Clear all nodes and reset."; st.button("🗑️ Reset Workflow", use_container_width=True, help=tooltip_reset, key="reset_workflow_btn", on_click=lambda: setattr(st.session_state, 'nodes', []) or st.rerun())
top_cols = st.columns([0.6, 0.4])
with top_cols[0]: # Graph Vis (No Change)
    st.subheader("📊 Workflow Graph")
    if not st.session_state.nodes: st.info("Add nodes or load an example.")
    elif not AGRAPH_AVAILABLE: st.warning("Install `streamlit-agraph` for visualization.")
    else:
        try:
            agraph_nodes, agraph_edges = generate_agraph_data(st.session_state.nodes); agraph_config = Config(width='100%', height=500, directed=True, physics={'enabled': True, 'solver': 'forceAtlas2Based', 'forceAtlas2Based': {'gravitationalConstant': -60, 'centralGravity': 0.01, 'springLength': 120, 'springConstant': 0.1, 'damping': 0.3}}, interaction={'navigationButtons': True, 'tooltipDelay': 300, 'hover': True}, nodes={'font': {'size': 14}}, edges={'font': {'size': 12, 'align': 'middle'}}, layout={'hierarchical': False}, manipulation=False )
            clicked_node_id = agraph(nodes=agraph_nodes, edges=agraph_edges, config=agraph_config); valid_node_ids = {n['id'] for n in st.session_state.nodes if isinstance(n, dict)}
            if clicked_node_id and clicked_node_id in valid_node_ids and clicked_node_id != st.session_state.selected_node_id: select_node(clicked_node_id); st.rerun()
        except Exception as e: st.error(f"Graph Error: {e}", icon="🔥"); print(f"Graph Error: {e}"); import traceback; traceback.print_exc()
with top_cols[1]: # Node Config (No Change)
    st.subheader("⚙️ Node Configuration"); valid_node_ids = [n.get('id') for n in st.session_state.nodes if isinstance(n, dict)]
    if not st.session_state.selected_node_id or st.session_state.selected_node_id not in valid_node_ids: st.session_state.selected_node_id = valid_node_ids[0] if valid_node_ids else None
    if not st.session_state.nodes: st.info("Add nodes or load example.")
    else:
        node_options_display = get_node_options_for_select(include_end=False); node_ids_only = [opt[0] for opt in node_options_display]; current_selection_index=0
        try: current_selection_index = node_ids_only.index(st.session_state.selected_node_id) if st.session_state.selected_node_id in node_ids_only else 0
        except: pass
        if not node_ids_only: current_selection_index = 0
        selected_id_from_dropdown = st.selectbox( "Select Node:", options=node_options_display, index=current_selection_index, format_func=lambda x: x[1], key="node_selector_config", label_visibility="collapsed" )
        if selected_id_from_dropdown and selected_id_from_dropdown[0] != st.session_state.selected_node_id: select_node(selected_id_from_dropdown[0]); st.rerun()
        st.divider()
    selected_node_data = next((n for n in st.session_state.nodes if isinstance(n, dict) and n.get("id") == st.session_state.selected_node_id), None)
    if selected_node_data:
         node_id, node_name, node_prompt = selected_node_data["id"], selected_node_data.get("name", ""), selected_node_data.get("prompt", ""); routing_rules = selected_node_data.get("routing_rules", {}); default_target = routing_rules.get("default_target", END_NODE_ID); conditional_targets = routing_rules.get("conditional_targets", [])
         if not isinstance(routing_rules, dict): routing_rules = {"default_target": END_NODE_ID, "conditional_targets": []}
         if not isinstance(conditional_targets, list): conditional_targets = []
         with st.container(border=True):
             form_key = f"config_form_{node_id}"
             with st.form(key=form_key):
                 st.markdown(f"**Editing: {node_name}** (`{node_id}`)"); edited_name = st.text_input("Node Name", value=node_name, key=f"cfg_name_{node_id}"); edited_prompt = st.text_area("LLM Prompt", value=node_prompt, height=150, key=f"cfg_prompt_{node_id}", help=f"Define task. Use '{{input_text}}' if needed. End response with '{ROUTING_KEY_MARKER} <key>'.")
                 st.markdown("**🚦 Routing Rules**"); node_options = get_node_options_for_select(include_end=True, exclude_node_id=node_id); current_default_idx=0;
                 try: current_default_idx = [i for i, (opt_id, _) in enumerate(node_options) if opt_id == default_target][0]
                 except: current_default_idx = next((i for i, (opt_id, _) in enumerate(node_options) if opt_id == END_NODE_ID), 0)
                 selected_default_option = st.selectbox("Default Target", options=node_options, index=current_default_idx, format_func=lambda x: x[1], key=f"cfg_default_{node_id}"); edited_default_target_id = selected_default_option[0] if selected_default_option else END_NODE_ID
                 st.markdown(f"**Conditional Targets (based on {ROUTING_KEY_MARKER} output):**"); edited_conditional_targets = []; current_conditional_targets = list(conditional_targets)
                 for rule_idx, rule in enumerate(current_conditional_targets):
                     st.caption(f"Rule {rule_idx+1}"); rule_cols = st.columns([0.5, 0.5]);
                     with rule_cols[0]: output_key = st.text_input(f"If Key Is", value=rule.get("output_key", ""), placeholder="e.g., success", key=f"cfg_key_{node_id}_{rule_idx}", label_visibility="collapsed")
                     with rule_cols[1]:
                          current_target_idx=0;
                          try: current_target_idx = [i for i, (opt_id, _) in enumerate(node_options) if opt_id == rule.get("target_node_id")][0]
                          except: current_target_idx = next((i for i, (opt_id, _) in enumerate(node_options) if opt_id == END_NODE_ID), 0)
                          selected_target_option = st.selectbox(f"Then Go To", options=node_options, index=current_target_idx, format_func=lambda x: x[1], key=f"cfg_target_{node_id}_{rule_idx}", label_visibility="collapsed"); target_node_id = selected_target_option[0] if selected_target_option else END_NODE_ID
                     edited_conditional_targets.append({"output_key": output_key.strip(), "target_node_id": target_node_id})
                 st.divider(); submitted = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                 if submitted:
                     final_conditional_targets = [r for r in edited_conditional_targets if r.get("output_key")]; new_data = {"name": edited_name.strip(), "prompt": edited_prompt, "routing_rules": {"default_target": edited_default_target_id, "conditional_targets": final_conditional_targets}}
                     if not edited_name.strip(): st.warning("Node Name cannot be empty.")
                     elif any(isinstance(n, dict) and n.get('id') != node_id and n.get('name','').strip() == edited_name.strip() for n in st.session_state.nodes): st.warning(f"Name exists.")
                     else: update_node_data_ui(node_id, new_data); st.rerun()
             st.markdown("**Manage Rules & Node:**"); action_cols = st.columns([0.5, 0.5])
             with action_cols[0]: st.button("➕ Add Rule", key=f"add_rule_btn_{node_id}", on_click=add_conditional_rule_ui, args=(node_id,), use_container_width=True)
             if conditional_targets: rule_opts = [(idx, f"Rule {idx+1}: '{rule.get('output_key', '')[:10]}...'") for idx, rule in enumerate(conditional_targets)]; rule_opts.insert(0, (-1, "Delete Rule...")); selected_rule_idx_to_del = st.selectbox("Delete Rule", options=rule_opts, format_func=lambda x: x[1], label_visibility="collapsed", index=0, key=f"del_rule_sel_{node_id}")
             if 'selected_rule_idx_to_del' in locals() and selected_rule_idx_to_del and selected_rule_idx_to_del[0] != -1: rule_idx_del = selected_rule_idx_to_del[0]; st.button(f"🗑️ Confirm Del Rule {rule_idx_del+1}", key=f"del_rule_btn_{node_id}_{rule_idx_del}", on_click=delete_conditional_rule_ui, args=(node_id, rule_idx_del), use_container_width=True, type="secondary")
             with action_cols[1]: current_node_index = next((i for i, n in enumerate(st.session_state.nodes) if isinstance(n, dict) and n.get("id") == node_id), -1); st.button("⬆️ Up", key=f"mv_up_{node_id}", on_click=move_node_ui, args=(node_id, -1), disabled=(current_node_index <= 0), use_container_width=True); st.button("⬇️ Down", key=f"mv_dn_{node_id}", on_click=move_node_ui, args=(node_id, 1), disabled=(current_node_index < 0 or current_node_index >= len(st.session_state.nodes) - 1), use_container_width=True); st.button("❌ Delete Node", key=f"del_nd_{node_id}", on_click=delete_node_ui, args=(node_id,), use_container_width=True, type="secondary", help="Delete this node.")
    elif st.session_state.nodes: st.info("Select node.");
    if st.session_state.selected_node_id and st.session_state.nodes and st.session_state.selected_node_id not in [n.get('id') for n in st.session_state.nodes if isinstance(n, dict)]: st.session_state.selected_node_id = st.session_state.nodes[0].get('id'); st.rerun()
    elif not st.session_state.nodes: st.session_state.selected_node_id = None

# --- Execution Section (Adapted for Dict State - No Change) ---
st.divider(); st.header("🚀 Execute Workflow")
run_tooltip = ""; run_disabled = True
if st.session_state.compiled_graph and llm_ready: st.success("Workflow compiled.", icon="✅"); run_tooltip = "Run workflow."; run_disabled = False
elif not llm_ready: st.warning("LLM not ready.", icon="⚠️"); run_tooltip = "LLM needs API Key."
elif st.session_state.nodes: st.warning("Compile Workflow first.", icon="⚠️"); run_tooltip = "Compile first."
else: st.info("Workflow empty."); run_tooltip = "Workflow empty/not compiled."
initial_message = st.text_area( "Enter initial message:", height=80, key="initial_input_exec", value="I want moderate capital appreciation over 5-7 years, willing to accept some market volatility but avoid highly speculative assets. Focus on tech and renewable energy sectors.", help="Input for the first node." )
if not initial_message.strip(): run_disabled = True; run_tooltip += " Initial message required."
if st.button("▶️ Run Workflow", disabled=run_disabled, type="primary", help=run_tooltip):
    st.session_state.execution_log = ["**🚀 Starting Workflow...**"]; st.session_state.final_state = None
    initial_state = WorkflowState(input=initial_message, node_outputs={}, last_response_content="", current_node_id="")
    st.session_state.execution_log.append(f"📥 Input: {initial_message[:150]}{'...' if len(initial_message)>150 else ''}")
    log_placeholder = st.empty(); log_placeholder.info("⏳ Running workflow...")
    with st.spinner("Executing workflow..."):
        try:
            rec_limit = st.session_state.get('recursion_limit', 25); print(f"Invoking graph with limit: {rec_limit}")
            final_state_result: WorkflowState = st.session_state.compiled_graph.invoke(initial_state, config={"recursion_limit": rec_limit})
            st.session_state.final_state = final_state_result; st.session_state.execution_log.append("**🏁 Workflow Finished**"); st.toast("Finished!", icon="🏁")
        except Exception as e:
            err_msg = f"{e}"
            if "must be followed by tool messages" in str(e): err_msg = f"LLM generated 'tool_calls' which graph cannot handle. Error: {e}."; st.error(f"{err_msg}", icon="🔥")
            elif isinstance(e, RecursionError) or "recursion limit" in str(e).lower(): err_msg = f"Recursion limit ({rec_limit}) reached. Error: {e}"; st.error(f"{err_msg}", icon="🔥")
            else: st.error(f"Exec failed: {err_msg}", icon="🔥");
            st.session_state.execution_log.append(f"**💥 WORKFLOW ERROR:** {err_msg}"); print(f"Exec Error: {e}"); import traceback; traceback.print_exc(); st.toast("Failed!", icon="❌")
    log_placeholder.empty(); st.rerun()

# --- Results Display Section (Adapted for Dict State - No Change) ---
st.subheader("📊 Execution Results"); results_cols = st.columns(2)
with results_cols[0]:
    st.markdown("**Execution Log**");
    if st.session_state.execution_log: log_text = "\n".join(st.session_state.execution_log); st.text_area("Log Details:", value=log_text, height=300, disabled=True, key="log_display_final_main")
    else: st.caption("Run workflow to see log.")
with results_cols[1]:
    st.markdown("**Final Output Message**"); final_message_content = None
    if st.session_state.final_state and isinstance(st.session_state.final_state, dict):
        final_content_raw = st.session_state.final_state.get('last_response_content', '')
        if final_content_raw and isinstance(final_content_raw, str): final_message_content = re.sub(rf"\s*{ROUTING_KEY_MARKER}\s*\w+\s*$", "", final_content_raw).strip()
    if final_message_content:
        message_container = st.container(height=300, border=False); avatar = "🏁";
        if any("WORKFLOW ERROR" in log for log in st.session_state.execution_log): avatar = "💥"
        elif "ERROR:" in final_message_content: avatar = "⚠️"
        message_container.chat_message("assistant", avatar=avatar).write(final_message_content)
    elif any("WORKFLOW ERROR" in log for log in st.session_state.execution_log): st.caption("Ended with error.")
    else: st.caption("Run workflow.")
