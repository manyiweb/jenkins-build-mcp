Use the `jenkinsBuild` MCP server for Jenkins build requests.
When the user asks to trigger a build, ask for the site if the same service exists in multiple site variants.
When the service, site, and branch are clear, call `trigger_build` directly.
