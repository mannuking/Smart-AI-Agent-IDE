import streamlit as st
import os
import json
import time
from typing import Optional, Dict, List, Any

from components.memory import GlobalMemory, LocalMemory
from components.attention_mechanism import AttentionMechanism
from components.node import Node
from components.utils import handle_node_retryable_error, MAX_DEPTH, MAX_RETRIES, RETRY_DELAY, GLOBAL_CONTEXT_SUMMARY_INTERVAL, STATUS_PENDING, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED
from components.file_manager import FileManager

class Agent:
    def __init__(self, llm, llm_config, global_context: str = "This agent decomposes complex tasks.") -> None:
        self.attention_mechanism = AttentionMechanism()
        self.global_memory = GlobalMemory()
        self.global_memory.update_context(global_context)
        self.llm = llm
        self.llm_config = llm_config
        self.execution_count = 0
        self.max_depth = MAX_DEPTH
        self.global_context_summary_interval = GLOBAL_CONTEXT_SUMMARY_INTERVAL
        self.file_manager = FileManager()

    def run(self, task_description: str, initial_constraints: Optional[list[str]] = None) -> None:
        self.reset_agent()
        root_node = self.create_root_node(task_description, initial_constraints)
        st.session_state.root_node_id = root_node.node_id
        # Automatically execute the root node to start the task decomposition
        self.agentFlow("execute", root_node)

    def reset_agent(self) -> None:
        st.session_state.node_lookup = {}
        if 'root_node_id' in st.session_state:
            del st.session_state.root_node_id
        if os.path.exists("agent_memory.json"):
            os.remove("agent_memory.json")
        self.setup_agent()
        st.session_state.selected_node_id = None
        st.session_state.previous_state = None

    def setup_agent(self) -> None:
        st.session_state.node_lookup = {}
        self.attention_mechanism.add_constraint_checker("format", self.attention_mechanism._check_json_format)
        self.attention_mechanism.add_constraint_checker("contains", self.attention_mechanism._check_contains_word)
        self.attention_mechanism.add_constraint_checker("max_length", self.attention_mechanism._check_max_length)
        self.attention_mechanism.add_constraint_checker("code", self.attention_mechanism._check_has_code)
        st.session_state.attention_mechanism = self.attention_mechanism
        st.session_state.agent = self
        st.session_state.llm = self.llm
        st.session_state.llm_config = self.llm_config

    def create_root_node(self, task_description: str, initial_constraints: Optional[list[str]] = None) -> Node:
        new_node = Node(parent_id=None, task_description=task_description, depth=0)
        st.session_state.node_lookup[new_node.node_id] = new_node
        if initial_constraints:
            for constraint in initial_constraints:
                st.session_state.attention_mechanism.add_constraint(new_node.node_id, constraint)
        st.session_state.attention_mechanism.track_dependencies(None, new_node.node_id)
        return new_node

    def create_child_node(self, parent_node: Node, task_description: str, depth: int) -> Node:
        new_node = Node(parent_id=parent_node.node_id, task_description=task_description, depth=depth)
        st.session_state.node_lookup[new_node.node_id] = new_node
        parent_node.add_child(new_node.node_id)
        st.session_state.attention_mechanism.track_dependencies(parent_node.node_id, new_node.node_id)
        return new_node

    def delete_node_and_children(self, node: Node) -> None:
        for child_id in node.child_ids:
            if child_id in st.session_state.node_lookup:
                self.delete_node_and_children(st.session_state.node_lookup[child_id])
        st.session_state.node_lookup.pop(node.node_id, None)
        st.session_state.attention_mechanism.remove_node(node.node_id)

    def agentFlow(self, action: str, node: Node, regeneration_guidance: str = "") -> None:
        if action == "execute":
            self._execute_node(node)
        elif action == "regenerate":
            self._regenerate_node(node, regeneration_guidance)
        elif action == "delete":
            self.delete_node_and_children(node)
        elif action == "select":
            self._select_node(node)
        else:
            raise ValueError(f"Invalid action: {action}")

    def _execute_node(self, node: Node) -> None:
        # Show loading spinner
        with st.spinner(f"Executing node: {node.retrieve_from_memory('task')}"):
            node.status = STATUS_RUNNING
            prompt = node.build_prompt()
            
            # Create separate containers for different sections without using expanders
            prompt_container = st.container()
            output_container = st.container()
            code_container = st.container()
            
            with prompt_container:
                st.markdown("### Executing Node")
                st.write("**Prompt sent to LLM:**")
                # Use a button to show the prompt instead of an expander
                if st.button("Show/Hide Prompt", key=f"show_prompt_{node.node_id}"):
                    st.code(prompt, language="text")

            success = False
            with output_container:
                for attempt in range(MAX_RETRIES):
                    try:
                        with st.spinner("Generating response..."):
                            response = self.llm.generate_content(
                                prompt,
                                generation_config=self.llm_config
                            )
                            llm_output = response.text
                        
                        if not llm_output or llm_output.strip() == "":
                            raise ValueError("Empty response from LLM")
                        
                        st.success("Response generated successfully")
                        # Use a container instead of an expander
                        st.markdown("**LLM Output:**")
                        output_viewer = st.container()
                        with output_viewer:
                            # Add button to toggle showing output
                            if st.button("Show/Hide Output", key=f"show_output_{node.node_id}"):
                                st.code(llm_output, language="text")

                        node.output = llm_output
                        
                        # Process the LLM output to extract subtasks
                        node.process_llm_output(llm_output)
                        
                        # Check if we got any valid results
                        if node.child_ids or node.retrieve_from_memory("result") or node.retrieve_from_memory("code_files"):
                            success = True
                        else:
                            # Try additional extraction methods
                            self._extract_code_from_json_output(node)
                            if node.retrieve_from_memory("code_files"):
                                success = True
                        
                        # Check constraints - if failed, continue trying
                        if not st.session_state.attention_mechanism.check_constraints(node):
                            success = False
                            continue
                        
                        break
                    except Exception as e:
                        st.error(f"Error in attempt {attempt+1}: {str(e)}")
                        if handle_node_retryable_error(node, attempt, e):
                            return
                
                # If we've exhausted all attempts but didn't succeed, mark as failed
                if not success and node.status != STATUS_FAILED:
                    node.status = STATUS_FAILED
                    node.error_message = "Failed to process LLM output after multiple attempts"
                    st.error("All attempts failed. Please try regenerating the node.")
                    return

            # Process code in output in a separate container
            if success:
                with code_container:
                    self._process_code_in_output(node, node.output)

                if node.status == STATUS_RUNNING:
                    node.status = STATUS_COMPLETED
                    if not node.child_ids:
                        st.session_state.attention_mechanism.summarize_node(node)
                        
                    # If root node, show the task decomposition
                    if node.node_id == st.session_state.root_node_id and node.child_ids:
                        st.write("**Task decomposed into the following subtasks:**")
                        for i, child_id in enumerate(node.child_ids):
                            if child_id in st.session_state.node_lookup:
                                child_node = st.session_state.node_lookup[child_id]
                                task = child_node.retrieve_from_memory("task")
                                st.write(f"{i+1}. {task}")

    def _process_code_in_output(self, node: Node, output: str) -> None:
        """Process and extract code from the node output"""
        # Containerize the code processing to prevent UI layout issues
        code_files = node.extract_code_files()
        
        if code_files:
            st.write("### Generated Code Files")
            st.write(f"Found {len(code_files)} code file(s)")
            
            # Store code files in session state for this node
            node_key = f"code_files_{node.node_id}"
            st.session_state[node_key] = code_files
            
            # Store the code files in node's memory
            node.store_in_memory("code_files", code_files)
            
            # Use session state for file selection instead of radio button
            file_selection_key = f"selected_file_idx_{node.node_id}"
            if file_selection_key not in st.session_state:
                st.session_state[file_selection_key] = 0
                
            # Get file names and create a selection widget
            file_names = list(code_files.keys())
            if not file_names:  # Safety check
                return
                
            # Select file using a selectbox (not inside a form)
            selected_idx = st.selectbox(
                "Select file to view:",
                range(len(file_names)),
                format_func=lambda i: file_names[i],
                key=file_selection_key
            )
            
            # Update selected file in session state
            selected_file = file_names[selected_idx]
            st.session_state[f"current_file_{node.node_id}"] = selected_file
            
            # Display the selected file's content
            content = code_files[selected_file]
            language = self.file_manager.get_language_from_extension(selected_file)
            
            # Display the code
            st.code(content, language=language)
            
            # Add save action - use separate button outside form context
            save_key = f"save_btn_{node.node_id}_{selected_file}"
            if st.button("Save File", key=save_key):
                success = self.file_manager.save_file(selected_file, content)
                if success:
                    st.success(f"File saved: {selected_file}")
                else:
                    st.error(f"Failed to save file: {selected_file}")
            
            # Add open in editor action
            editor_key = f"editor_btn_{node.node_id}_{selected_file}"
            if st.button("Open in Editor", key=editor_key):
                st.session_state.active_file = selected_file
                st.session_state.file_content = content
                st.experimental_rerun()

    def _extract_code_from_json_output(self, node: Node) -> None:
        """Extract code from JSON output and create files for it."""
        try:
            # Try to parse the output as JSON
            import json
            try:
                output_json = json.loads(node.output)
            except json.JSONDecodeError:
                # Try to extract JSON part from the text
                import re
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', node.output)
                if json_match:
                    try:
                        output_json = json.loads(json_match.group(1))
                    except:
                        return
                else:
                    return
                
            # Look for code in JSON fields
            code_files = {}
            
            # Common patterns for code fields in JSON
            if "code" in output_json and isinstance(output_json["code"], str):
                # Simple code field - generate a default filename
                extension = "py" if "python" in node.output.lower() else "js"
                code_files[f"script.{extension}"] = output_json["code"]
                
            # Check for files/implementations array
            for field_name in ["files", "implementation", "code_files"]:
                if field_name in output_json and isinstance(output_json[field_name], list):
                    for i, file_info in enumerate(output_json[field_name]):
                        if isinstance(file_info, dict):
                            # Extract filename and code from dict
                            filename = file_info.get("filename", file_info.get("path", f"file_{i}.py"))
                            code = file_info.get("content", file_info.get("code", ""))
                            if code:
                                code_files[filename] = code
                        elif isinstance(file_info, str) and i % 2 == 0:
                            # Check if alternating entries are filename/content pairs
                            if i+1 < len(output_json[field_name]) and isinstance(output_json[field_name][i+1], str):
                                code_files[file_info] = output_json[field_name][i+1]
            
            # Store extracted code files in memory
            if code_files:
                current_files = node.retrieve_from_memory("code_files") or {}
                current_files.update(code_files)
                node.store_in_memory("code_files", current_files)
                
        except Exception as e:
            # Just log the error but don't crash
            print(f"Error extracting code from JSON: {str(e)}")

    def _regenerate_node(self, node: Node, regeneration_guidance: str) -> None:
        node.status = STATUS_PENDING
        node.output = ""
        node.error_message = ""
        node.store_in_memory("regeneration_guidance", regeneration_guidance)
        # Remove all child nodes
        for child_id in node.child_ids[:]:
            if child_id in st.session_state.node_lookup:
                self.delete_node_and_children(st.session_state.node_lookup[child_id])
        node.child_ids = []
        # Re-execute the node
        self._execute_node(node)

    def _select_node(self, node: Node) -> None:
        """Handle node selection for continuation or detailed execution"""
        st.session_state.selected_node_id = node.node_id
        if node.status == STATUS_PENDING:
            self._execute_node(node)
        elif node.status == STATUS_COMPLETED and node.child_ids:
            # Show children and allow selection
            st.write(f"Selected node: {node.retrieve_from_memory('task')}")
            st.write("This node has been completed. You can select a child node to continue.")
        else:
            st.write(f"Selected node: {node.retrieve_from_memory('task')}")
            st.write("What would you like to do with this node?")
            
            # Add options for continuing/extending this node
            new_task = st.text_area("Specify a follow-up task or further details:", key=f"follow_up_{node.node_id}")
            if st.button("Continue with this detail", key=f"cont_{node.node_id}"):
                # Create a new child node with the specified task
                if new_task.strip():
                    new_node = self.create_child_node(node, new_task, node.depth + 1)
                    self._execute_node(new_node)
    
    def save_session(self, filename: str) -> None:
        data = {
            "node_lookup": {node_id: {k: v for k, v in node.__dict__.items() if k != 'local_memory'} for node_id, node in st.session_state.node_lookup.items()},
            "attention_mechanism": {
                "dependency_graph": st.session_state.attention_mechanism.dependency_graph,
                "constraints": st.session_state.attention_mechanism.constraints,
            },
            "root_node_id": st.session_state.root_node_id,
            "global_memory": st.session_state.agent.global_memory.global_context,
            "execution_count": st.session_state.agent.execution_count
        }

        for node_id, node_data in data["node_lookup"].items():
            node_data["local_memory"] = node_data["local_memory"].local_memory

        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

    def load_session(self, filename: str) -> None:
        with open(filename, "r") as f:
            data = json.load(f)

        self.reset_agent()

        st.session_state.root_node_id = data["root_node_id"]
        st.session_state.node_lookup = {}
        
        # Fix the node loading process
        for node_id, node_data in data["node_lookup"].items():
            task_description = node_data.get("task_description")
            if not task_description and "local_memory" in node_data:
                # Try to get task from local memory
                if "task" in node_data["local_memory"]:
                    task_description = node_data["local_memory"]["task"]
                    
            new_node = Node(
                parent_id=node_data["parent_id"], 
                task_description=task_description, 
                depth=node_data.get("depth", 0)
            )
            new_node.node_id = node_data["node_id"]
            new_node.child_ids = node_data["child_ids"]
            new_node.status = node_data["status"]
            new_node.output = node_data["output"]
            new_node.error_message = node_data.get("error_message", "")
            
            # Properly initialize the local memory
            new_node.local_memory = LocalMemory(new_node.node_id)
            if "local_memory" in node_data and isinstance(node_data["local_memory"], dict):
                for key, value in node_data["local_memory"].items():
                    new_node.local_memory.store(key, value)
                    
            st.session_state.node_lookup[node_id] = new_node

        # Set up attention mechanism and constraints
        st.session_state.attention_mechanism.dependency_graph = data["attention_mechanism"]["dependency_graph"]
        st.session_state.attention_mechanism.constraints = data["attention_mechanism"]["constraints"]
        
        # Update global memory
        self.global_memory.update_context(data["global_memory"])
        self.execution_count = data["execution_count"]
