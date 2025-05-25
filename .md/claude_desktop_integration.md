# Connecting Claude Desktop with NexusMind

This guide will help you set up Claude Desktop to use the NexusMind Graph of Thoughts server for enhanced scientific reasoning.

## Prerequisites

1. NexusMind server running (either locally or in a Docker container)
2. Claude Desktop application installed on your computer
3. Access to Claude 3.7 Sonnet model

## Step 1: Configure the MCP Connection in Claude Desktop

1. Open Claude Desktop
2. Navigate to Settings (gear icon)
3. Go to "Tools" or "Integrations" section
4. Click "Add Tool" or "Add Integration" 
5. Select "MCP Integration" or "Custom Server"
6. Import the `claude_mcp_config.json` file from this repository

Alternatively, you can manually configure the connection with the following settings:

- **Name**: NexusMind MCP Integration
- **Description**: Integrates Claude with the NexusMind server for advanced scientific reasoning
- **Icon**: 🔬
- **Endpoint**: http://localhost:8000/mcp
- **Method**: POST
- **Headers**: Content-Type: application/json

## Step 2: Test the Connection

1. In Claude Desktop, create a new conversation
2. Ensure the Claude 3.7 Sonnet model is selected
3. Enable the NexusMind integration from the tools panel
4. Ask a scientific reasoning question, for example:
   - "What is the relationship between climate change and ocean acidification?"
   - "Explain how mRNA vaccines work and compare them to traditional vaccines."
   - "What are the current theories about dark matter and dark energy?"

## Step 3: Using the Integration

When you ask a question, Claude Desktop will:

1. Send your query to the NexusMind MCP server
2. The server will process it through the Graph of Thoughts reasoning process
3. Return a structured response with:
   - The answer to your question
   - The reasoning trace showing the thought process
   - The graph state representation of the reasoning

## Troubleshooting

If you encounter issues:

1. Check that the NexusMind server is running by visiting http://localhost:8000/health
2. Verify your network connection and firewall settings
3. Check the NexusMind server logs for error messages
4. Ensure the Claude Desktop app has the correct MCP configuration

## Advanced Configuration

For advanced users, you can modify the `claude_mcp_config.json` file to:

- Change the parameters for the reasoning process
- Adjust the level of detail in the responses
- Configure how graph state information is displayed

## Detailed Logging

To help identify errors during the 8-stage process, detailed logging has been added. Each stage logs its start and end, along with any significant events or errors. This logging can be found in the server logs.

## Error Handling

Error handling has been implemented for each stage to catch and log exceptions. If an error occurs, it will be logged with details about the stage and the nature of the error. This information can be used to diagnose and fix issues.

## Input Validation

Input parameters are validated to ensure they meet expected formats. If invalid parameters are detected, an error will be logged and an appropriate response will be returned to the client.
