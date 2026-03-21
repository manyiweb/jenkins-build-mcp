# ChatGPT Remote MCP Notes

To use this project with ChatGPT, deploy it as a remote `streamable-http` MCP server.

Start it like this:

```bash
jenkins-build-mcp --env-file /opt/jenkins-build-mcp/.env.local --transport streamable-http --host 0.0.0.0 --port 8000
```
