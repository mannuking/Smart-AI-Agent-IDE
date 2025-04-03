# Smart Agent IDE: A Hierarchical Task Decomposition System Powered by Large Language Models

A Project proposal submitted towards the fulfillment of the requirement. 
 
Bachelor of Technology In Computer Engineering 
Submitted by 
Jai Kumar Meena 2K21/CO/209
Jai Verma
2K21/CO/210
Jay Kumar Bharti
2K21/CO/214
 
Submitted to  
Prof. Gull Kaur 

  
DELHI TECHNOLOGICAL UNIVERSITY  
(FORMERLY Delhi College of Engineering) 
Bawana Road, Delhi-110042 
 
 
## Introduction 
Software development involves breaking down complex problems into manageable subtasks, a process that often requires significant cognitive effort and expertise. The Smart Agent IDE project aims to leverage Large Language Models (LLMs) to assist developers in this decomposition process, providing an intelligent development environment that can automatically break down complex programming tasks into hierarchical subtasks and generate implementation code. By integrating advanced AI capabilities with traditional IDE features, the system streamlines the software development workflow and enhances productivity.
 
## Objectives of the Project 
The primary objectives are as follows: 
1. Design and develop an intelligent IDE that utilizes hierarchical task decomposition to break down complex programming problems
 
2. Implement a sophisticated agent system with dual-memory architecture (local and global memory) for effective context management
 
3. Create an attention mechanism that manages constraints and dependencies between tasks using graph-based tracking
 
4. Integrate code generation capabilities powered by Google Gemini Pro to implement subtasks automatically
 
5. Develop a comprehensive user interface with interactive task visualization, integrated code editor, and terminal functionality
 
 
## Feasibility Study 
A preliminary study has been conducted considering the required computational resources and software tools. Necessary resources include: 
- Access to Google Generative AI APIs for the Gemini models
- Computational resources for running the Streamlit application and handling LLM requests
- Appropriate software such as Streamlit for user interface development, Networkx for graph visualization, and Streamlit-Ace for the code editor component
- Knowledge of prompt engineering and LLM optimization techniques

The project is feasible considering existing computational resources, software tools availability, and the team's expertise in AI-assisted programming and software engineering.
 
## Methodology 
The project methodology includes the following phases: 

1. Agent System Architecture:
   a. Implementation of a modular agent design with task planning and execution engine
   b. Development of a dynamic constraint system for output validation
   c. Creation of session management for persisting complex graph structures

2. Memory Management Implementation:
   a. Design of local memory for task-specific context isolation
   b. Implementation of global memory for shared information across nodes
   c. Development of context window optimization through strategic summarization

3. Attention Mechanism Development:
   a. Creation of a constraint system with declarative constraint definition
   b. Implementation of dependency graph for tracking task relationships
   c. Development of focus management techniques to direct agent attention

4. User Interface Engineering:
   a. Design of interactive task visualization with hierarchical tree and network graph views
   b. Integration of code editor with syntax highlighting and AI assistance
   c. Development of terminal interface with command execution capabilities

5. Testing & Evaluation:
   a. Performance evaluation of LLM optimization strategies
   b. User experience testing for interface responsiveness and usability
   c. Assessment of task decomposition quality and code generation accuracy

## Facilities Required: 
➢ High-capacity computational resources for handling LLM requests
➢ Access to necessary software and programming libraries (Python, Streamlit, Networkx, Matplotlib)
➢ Google API key for accessing Gemini models
➢ Development environment with sufficient storage for project files and generated code

## Bibliography: 
[1] Erol, K., Hendler, J., & Nau, D. S. (1994). HTN planning: Complexity and expressivity. AAAI, 94, 1123-1128.
[2] Wei, J. et al. (2022). Chain of thought prompting elicits reasoning in large language models. arXiv preprint arXiv:2201.11903.
[3] Yao, S. et al. (2023). Tree of thoughts: Deliberate problem solving with large language models. arXiv preprint.
[4] Yao, S. et al. (2022). ReAct: Synergizing reasoning and acting in language models. arXiv preprint.
[5] Kotseruba, I., & Tsotsos, J. K. (2020). 40 years of cognitive architectures: Core cognitive abilities and practical applications.
