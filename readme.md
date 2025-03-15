# Smart Agent IDE

## Overview

Smart Agent IDE is an innovative development environment that combines AI-powered task decomposition with code generation capabilities. Built on Streamlit and powered by Google's Gemini models, this IDE helps developers break down complex tasks into manageable subtasks and generates code to implement them.

![Smart Agent IDE Screenshot](https://placeholder-for-screenshot.com/smart-agent-ide.png)

## Key Features

- **Hierarchical Task Decomposition**: Break complex programming problems into structured subtasks
- **AI-Powered Code Generation**: Generate implementation code for each subtask
- **Dynamic Task Graph**: Visualize task relationships with interactive graph and tree views
- **Integrated Code Editor**: Edit and save generated code directly in the IDE
- **Terminal Integration**: Execute commands and run code in the built-in terminal
- **File Explorer**: Browse and manage project files
- **Session Management**: Save and load work sessions for continuity
- **Model Configuration**: Fine-tune AI parameters for optimal performance

## System Architecture

Smart Agent IDE follows a modular architecture:

```
Smart Agent IDE
├── app.py                 # Main application entry point
├── components/            # Core UI and functionality components
│   ├── agent.py           # Agent logic for task decomposition
│   ├── node.py            # Node structure for task hierarchy
│   ├── file_explorer.py   # File system navigation
│   ├── terminal.py        # Command line interface
│   ├── editor.py          # Code editing component
│   ├── graph_view.py      # Task visualization
│   └── utils.py           # Utility functions and constants
├── agent/                 # Enhanced agent implementation (optional)
│   ├── constants.py       # Agent constants
│   ├── node.py            # Extended node functionality
│   └── memory.py          # Memory management system
└── requirements.txt       # Project dependencies
```

### Core Components

1. **Agent System**
   - Task decomposition engine
   - Execution flow management
   - Memory system integration

2. **Memory System**
   - Local Memory: Node-specific context
   - Global Memory: Cross-node shared information
   - Context summarization

3. **Node Structure**
   - Task representation
   - Status tracking (pending, running, completed, failed)
   - Parent-child relationships

4. **User Interface**
   - Split-panel layout with responsive design
   - Task visualization (tree and graph views)
   - Code editor with syntax highlighting
   - Resizable terminal interface
   - File explorer sidebar

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Google API key for Gemini models

### Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/yourusername/smart-agent-ide.git
cd smart-agent-ide
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Set up your Google API key:
   - Create a secrets.toml file in the project root
   - Add your API key: `GOOGLE_API_KEY = "your-google-api-key-here"`

4. Launch the application:
```bash
streamlit run app.py
```

## Usage Guide

### Creating a New Task

1. Enter a description of your programming task in the task input area
2. Add optional constraints:
   - Toggle "Require JSON" if you need structured JSON output
   - Toggle "Generate code" to instruct the agent to create implementation code
   - Add custom constraints as needed
3. Click "Run Task" to begin the task decomposition process

### Working with Task Trees

The agent will break down your task into subtasks and display them in either:
- **Task Tree View**: Hierarchical display of tasks with parent-child relationships
- **Graph View**: Visual network representation of tasks and their connections

For each task node:
1. Click "Select" to view details and output
2. Use "Execute" to run pending tasks
3. Use "Regenerate" to retry completed tasks with additional guidance
4. For completed tasks, add child tasks manually when needed

### Using the Code Editor

- View and edit generated code in the integrated editor
- Save files to disk with the "Save" button
- Open existing files through the File Explorer

### Managing Sessions

- Save your current session for later use
- Load previous sessions to continue your work
- Create new tasks without losing previous work

### Configuring Settings

Access settings through the sidebar to configure:
- **Model Selection**: Choose between various Gemini models
- **LLM Configuration**: Adjust temperature, top_p, top_k, and token limits
- **Terminal Settings**: Customize terminal height and behavior
- **Agent Configuration**: Set maximum tree depth and context summary intervals

## Example Workflow

1. **Define Task**: Enter "Create a Python web scraper that extracts product prices from an e-commerce site"
2. **Task Decomposition**: The agent breaks this down into subtasks:
   - Set up HTTP request handling
   - Create HTML parsing functions
   - Implement product data extraction
   - Add error handling and retries
   - Create data storage mechanism
3. **Execute Subtasks**: Select and execute each subtask to generate code
4. **Review & Edit**: Use the editor to modify generated code as needed
5. **Test Components**: Run code in the terminal to test functionality
6. **Complete Integration**: Combine components into the final solution

## Advanced Features

### Custom Task Creation

Add manual subtasks to extend the agent's decomposition:
1. Select a completed node
2. Use "Add Child Task" to create a new subtask
3. Enter your task description
4. Execute the new task for further processing

### Code File Management

When code is generated:
1. View all generated files in the node details
2. Save files directly to your filesystem
3. Open in the editor for further modification
4. Run and test code through the integrated terminal

### Agent Configuration

Fine-tune the agent's behavior:
- Adjust maximum tree depth to control task granularity
- Set summary intervals for context management
- Configure model parameters for different generation styles

## Development and Extension

This project is designed to be extensible. Key areas for extension:

- **Custom Agents**: Add specialized agents in the agent/ directory
- **UI Components**: Extend the components/ modules for additional features
- **Model Integration**: Add support for other AI models beyond Gemini

## Requirements

- streamlit
- google-generativeai
- networkx
- matplotlib
- streamlit-ace
- pathlib

## License

[Insert your license information here]

## Acknowledgments

- Built with Streamlit (https://streamlit.io)
- Powered by Google Generative AI (Gemini models)

---

*Smart Agent IDE - Transform your coding workflow with intelligent task decomposition.*
