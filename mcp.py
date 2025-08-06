import openai
import json
import time
import requests
import asyncio
import subprocess
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MCPServer:
    """Configuration for an MCP server"""
    name: str
    command: List[str]
    args: List[str] = None
    env: Dict[str, str] = None
    description: str = ""
    
    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.env is None:
            self.env = {}

class MCPManager:
    """Manager for MCP servers and tools"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.active_connections: Dict[str, subprocess.Popen] = {}
        self.available_tools: Dict[str, Dict] = {}
        
    def add_server(self, server: MCPServer):
        """Add an MCP server configuration"""
        self.servers[server.name] = server
        logger.info(f"Added MCP server: {server.name}")
    
    def add_default_servers(self):
        """Add some common MCP servers"""
        # File system MCP server
        self.add_server(MCPServer(
            name="filesystem",
            command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
            args=["/path/to/allowed/directory"],
            description="File system access for reading/writing files"
        ))
        
        # SQLite MCP server
        self.add_server(MCPServer(
            name="sqlite",
            command=["npx", "-y", "@modelcontextprotocol/server-sqlite"],
            args=["--db-path", "./database.sqlite"],
            description="SQLite database access"
        ))
        
        # Web search MCP server
        self.add_server(MCPServer(
            name="brave-search",
            command=["npx", "-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": "your-brave-api-key"},
            description="Web search capabilities"
        ))
        
        # GitHub MCP server
        self.add_server(MCPServer(
            name="github",
            command=["npx", "-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": "your-github-token"},
            description="GitHub repository access"
        ))
    
    async def start_server(self, server_name: str) -> bool:
        """Start an MCP server"""
        if server_name not in self.servers:
            logger.error(f"Server {server_name} not found")
            return False
            
        server = self.servers[server_name]
        
        try:
            # Create environment with server-specific variables
            env = os.environ.copy()
            env.update(server.env)
            
            # Start the server process
            cmd = server.command + server.args
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
            
            self.active_connections[server_name] = process
            logger.info(f"Started MCP server: {server_name}")
            
            # Initialize connection and get available tools
            await self._initialize_server(server_name)
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server {server_name}: {e}")
            return False
    
    async def _initialize_server(self, server_name: str):
        """Initialize connection with MCP server and get available tools"""
        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "LM Studio Chatbot",
                        "version": "1.0.0"
                    }
                }
            }
            
            process = self.active_connections[server_name]
            process.stdin.write(json.dumps(init_request) + "\n")
            process.stdin.flush()
            
            # Read response
            response = process.stdout.readline()
            if response:
                data = json.loads(response.strip())
                logger.info(f"Server {server_name} initialized: {data}")
                
                # Get available tools
                await self._get_tools(server_name)
                
        except Exception as e:
            logger.error(f"Failed to initialize server {server_name}: {e}")
    
    async def _get_tools(self, server_name: str):
        """Get available tools from MCP server"""
        try:
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            process = self.active_connections[server_name]
            process.stdin.write(json.dumps(tools_request) + "\n")
            process.stdin.flush()
            
            response = process.stdout.readline()
            if response:
                data = json.loads(response.strip())
                if "result" in data and "tools" in data["result"]:
                    tools = data["result"]["tools"]
                    self.available_tools[server_name] = tools
                    logger.info(f"Got {len(tools)} tools from {server_name}")
                    
        except Exception as e:
            logger.error(f"Failed to get tools from {server_name}: {e}")
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on an MCP server"""
        if server_name not in self.active_connections:
            raise Exception(f"Server {server_name} not connected")
        
        try:
            tool_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            process = self.active_connections[server_name]
            process.stdin.write(json.dumps(tool_request) + "\n")
            process.stdin.flush()
            
            response = process.stdout.readline()
            if response:
                data = json.loads(response.strip())
                return data
                
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {server_name}: {e}")
            raise
    
    def stop_server(self, server_name: str):
        """Stop an MCP server"""
        if server_name in self.active_connections:
            process = self.active_connections[server_name]
            process.terminate()
            del self.active_connections[server_name]
            logger.info(f"Stopped MCP server: {server_name}")
    
    def stop_all_servers(self):
        """Stop all MCP servers"""
        for server_name in list(self.active_connections.keys()):
            self.stop_server(server_name)
    
    def get_server_status(self) -> Dict[str, str]:
        """Get status of all servers"""
        status = {}
        for name, server in self.servers.items():
            if name in self.active_connections:
                process = self.active_connections[name]
                if process.poll() is None:
                    status[name] = "running"
                else:
                    status[name] = "stopped"
            else:
                status[name] = "not_started"
        return status
    
    def get_available_tools_list(self) -> List[Dict[str, Any]]:
        """Get a list of all available tools across all servers"""
        all_tools = []
        for server_name, tools in self.available_tools.items():
            for tool in tools:
                tool_info = tool.copy()
                tool_info["server"] = server_name
                all_tools.append(tool_info)
        return all_tools


class LMStudioMCPChatbot:
    def __init__(self, base_url="http://192.168.114.46:1234/v1", api_key="lm-studio"):
        self.base_url = base_url
        self.api_key = api_key
        self.client = openai.OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.conversation_history: List[dict] = []
        self.mcp_manager = MCPManager()
        self.mcp_enabled = False
        
        # Add default MCP servers
        self.mcp_manager.add_default_servers()

    def test_connection(self) -> bool:
        try:
            response = requests.get(self.base_url.replace("/v1", "/health"), timeout=5)
            return response.status_code == 200
        except Exception:
            try:
                self.client.models.list()
                return True
            except Exception:
                return False

    def add_system_prompt(self, prompt: str):
        # Enhanced system prompt with MCP capabilities
        mcp_tools_info = ""
        if self.mcp_enabled:
            tools = self.mcp_manager.get_available_tools_list()
            if tools:
                mcp_tools_info = f"\n\nYou have access to the following tools via MCP:\n"
                for tool in tools:
                    mcp_tools_info += f"- {tool['name']} ({tool['server']}): {tool.get('description', 'No description')}\n"
                mcp_tools_info += "\nYou can use these tools to help users with various tasks."
        
        enhanced_prompt = prompt + mcp_tools_info
        self.conversation_history.append({"role": "system", "content": enhanced_prompt})

    def get_available_models(self) -> List[str]:
        try:
            return [m.id for m in self.client.models.list().data]
        except Exception as exc:
            return [f"Error: {exc}"]

    async def enable_mcp(self, servers: List[str] = None):
        """Enable MCP and start specified servers"""
        if servers is None:
            servers = ["filesystem", "sqlite"]  # Default servers
        
        for server_name in servers:
            success = await self.mcp_manager.start_server(server_name)
            if success:
                logger.info(f"MCP server {server_name} started successfully")
            else:
                logger.error(f"Failed to start MCP server {server_name}")
        
        self.mcp_enabled = True
        logger.info("MCP enabled")

    def disable_mcp(self):
        """Disable MCP and stop all servers"""
        self.mcp_manager.stop_all_servers()
        self.mcp_enabled = False
        logger.info("MCP disabled")

    def get_mcp_status(self) -> Dict[str, Any]:
        """Get MCP status and available tools"""
        return {
            "enabled": self.mcp_enabled,
            "servers": self.mcp_manager.get_server_status(),
            "tools": self.mcp_manager.get_available_tools_list()
        }

    def chat(self, message: str, model_name: Optional[str] = None) -> str:
        self.conversation_history.append({"role": "user", "content": message})
        try:
            if not model_name:
                available = self.get_available_models()
                if not available or available[0].startswith("Error"):
                    raise RuntimeError("No models available in LM Studio")
                model_name = available[0]

            response = self.client.chat.completions.create(
                model=model_name,
                messages=self.conversation_history,
                temperature=0.7,
                max_tokens=1000,
                stream=False,
            )
            assistant_msg = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            return assistant_msg
        except Exception as exc:
            return f"Error: {exc}"

    def stream_chat(self, message: str, model_name: Optional[str] = None):
        self.conversation_history.append({"role": "user", "content": message})
        try:
            if not model_name:
                available = self.get_available_models()
                if not available or available[0].startswith("Error"):
                    raise RuntimeError("No models available in LM Studio")
                model_name = available[0]

            response = self.client.chat.completions.create(
                model=model_name,
                messages=self.conversation_history,
                temperature=0.7,
                max_tokens=1000,
                stream=True,
            )

            full = ""
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    yield delta
            self.conversation_history.append({"role": "assistant", "content": full})
        except Exception as exc:
            yield f"Error: {exc}"

    def clear_conversation(self):
        self.conversation_history = []

    def save_conversation(self, filename: str):
        with open(filename, "w", encoding="utf-8") as fp:
            json.dump(self.conversation_history, fp, indent=2, ensure_ascii=False)

    def load_conversation(self, filename: str):
        with open(filename, "r", encoding="utf-8") as fp:
            self.conversation_history = json.load(fp)


class LMStudioMCPWebChatbot:
    def __init__(self, chatbot: LMStudioMCPChatbot):
        self.chatbot = chatbot

    def create_app(self):
        from flask import Flask, render_template_string, request, jsonify, Response, send_file

        app = Flask(__name__)

        # Load the HTML template with MCP enhancements
        with open("chat_ui_mcp.html", "r", encoding="utf-8") as f:
            HTML_TEMPLATE = f.read()

        @app.route('/')
        def index():
            return render_template_string(HTML_TEMPLATE)

        @app.route('/api/status')
        def api_status():
            try:
                return (
                    jsonify({"status": "connected"})
                    if self.chatbot.test_connection()
                    else jsonify({"status": "error", "message": "Cannot connect to LM Studio"})
                )
            except Exception as exc:
                return jsonify({"status": "error", "message": str(exc)})

        @app.route('/api/models')
        def api_models():
            return jsonify({"models": self.chatbot.get_available_models()})

        @app.route('/api/chat', methods=['POST'])
        def api_chat():
            data = request.get_json(force=True)
            return jsonify({"response": self.chatbot.chat(data["message"], data.get("model"))})

        @app.route('/api/chat/stream', methods=['POST'])
        def api_chat_stream():
            data = request.get_json(force=True)

            def gen():
                for chunk in self.chatbot.stream_chat(data["message"], data.get("model")):
                    yield chunk
            return Response(gen(), mimetype='text/plain')

        @app.route('/api/clear', methods=['POST'])
        def api_clear():
            self.chatbot.clear_conversation()
            return jsonify({"status": "cleared"})

        @app.route('/api/download')
        def api_download():
           
            import tempfile, os
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
            json.dump(self.chatbot.conversation_history, fp, indent=2, ensure_ascii=False)
            fp.close()
            resp = send_file(fp.name, as_attachment=True, download_name="chat_history.json")

            @resp.call_on_close
            def _cleanup():
                os.unlink(fp.name)
            return resp

        # MCP-specific endpoints
        @app.route('/api/mcp/enable', methods=['POST'])
        def api_mcp_enable():
            try:
                data = request.get_json(force=True)
                servers = data.get("servers", ["filesystem", "sqlite"])
                
                # Run async function in sync context
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.chatbot.enable_mcp(servers))
                loop.close()
                
                return jsonify({"status": "enabled", "servers": servers})
            except Exception as exc:
                return jsonify({"status": "error", "message": str(exc)})

        @app.route('/api/mcp/disable', methods=['POST'])
        def api_mcp_disable():
            try:
                self.chatbot.disable_mcp()
                return jsonify({"status": "disabled"})
            except Exception as exc:
                return jsonify({"status": "error", "message": str(exc)})

        @app.route('/api/mcp/status')
        def api_mcp_status():
            return jsonify(self.chatbot.get_mcp_status())

        @app.route('/api/mcp/tools')
        def api_mcp_tools():
            return jsonify({"tools": self.chatbot.mcp_manager.get_available_tools_list()})

        return app


async def run_cli():
    print("🤖 LM Studio MCP Chatbot – CLI")
    bot = LMStudioMCPChatbot()
    print("🔄 Connecting…", end=" ")
    if not bot.test_connection():
        print("❌ failed\nEnsure LM Studio is running and reachable at http://192.168.114.46:1234")
        return
    print("✅ connected!")

    models = bot.get_available_models()
    if not models or models[0].startswith("Error"):
        print("❌ No models exposed in LM Studio")
        return

    current_model = models[0]
    bot.add_system_prompt("You are a helpful AI assistant with access to various tools via MCP.")
    
    print("🔧 Would you like to enable MCP? (y/n): ", end="")
    enable_mcp = input().lower().startswith('y')
    
    if enable_mcp:
        print("🚀 Enabling MCP servers...")
        await bot.enable_mcp()
        print("✅ MCP enabled!")
    
    print("Type 'quit' to exit, 'clear' to reset, 'models' to list models, 'mcp' for MCP status, or 'switch <n>'…")

    while True:
        try:
            user = input("\nYou ▶︎ ").strip()
            if user.lower() in {"quit", "exit", "q"}:
                break
            if user.lower() == "clear":
                bot.clear_conversation()
                bot.add_system_prompt("You are a helpful AI assistant with access to various tools via MCP.")
                print("History cleared.")
                continue
            if user.lower() == "models":
                for i, m in enumerate(models, 1):
                    print(f" {i}. {m}{' ←' if m==current_model else ''}")
                continue
            if user.lower() == "mcp":
                status = bot.get_mcp_status()
                print(f"MCP Status: {'Enabled' if status['enabled'] else 'Disabled'}")
                print(f"Servers: {status['servers']}")
                print(f"Available tools: {len(status['tools'])}")
                continue
            if user.startswith("switch "):
                try:
                    idx = int(user.split()[1])-1
                    if 0 <= idx < len(models):
                        current_model = models[idx]
                        print("Switched to", current_model)
                    else:
                        print("Invalid index")
                except ValueError:
                    print("Usage: switch <number>")
                continue
            if not user:
                continue
            print("Bot ▶︎ ", end="", flush=True)
            for chunk in bot.stream_chat(user, current_model):
                print(chunk, end="", flush=True)
            print()
        except KeyboardInterrupt:
            break
    
    # Clean up MCP connections
    bot.disable_mcp()


def main():
    print("≡ LM Studio MCP Chatbot Launcher ≡")
    print("1 ▶︎ CLI")
    print("2 ▶︎ Web UI")
    print("3 ▶︎ Exit")
    choice = input("Select 1-3: ").strip()
    if choice == "1":
        asyncio.run(run_cli())
    elif choice == "2":
        web = LMStudioMCPWebChatbot(LMStudioMCPChatbot()).create_app()
        if web:
            print("Open http://localhost:5000  (CTRL-C to quit)")
            web.run(host="0.0.0.0", port=5000, debug=False)
    else:
        print("Bye ✌️")


if __name__ == "__main__":
    main()