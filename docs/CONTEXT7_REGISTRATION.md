# Context7 Registration Guide for RFS Framework

## Overview

This guide explains how to register the RFS Framework in Context7, making it accessible to AI assistants and code editors that support the Model Context Protocol (MCP).

## What is Context7?

Context7 is a documentation system by Upstash that provides up-to-date, version-specific library documentation to AI language models and code editors. It prevents outdated code generation and ensures AI assistants have access to current documentation.

### Benefits of Context7 Registration

- ✅ **Current Documentation**: AI assistants access the latest RFS Framework docs
- ✅ **Accurate Code Generation**: Prevents hallucinated APIs and outdated patterns
- ✅ **Version Awareness**: Supports version-specific documentation
- ✅ **Wide Compatibility**: Works with Claude Desktop, Cursor, and other MCP-compatible tools
- ✅ **Automatic Updates**: Documentation stays synchronized with your repository

## Registration Methods

### Method 1: Web Interface (Recommended)

The easiest way to register RFS Framework in Context7:

1. **Visit Context7 Add Library Page**
   ```
   https://context7.com/add-library?tab=github
   ```

2. **Provide Repository Information**
   - Repository URL: `https://github.com/interactord/rfs-framework`
   - Primary Branch: `main`
   - Documentation Path: `/` (root, as we have docs throughout)

3. **Submit Registration**
   - Click "Add Library"
   - Context7 will automatically parse and index the documentation
   - You'll receive a confirmation with the library ID

4. **Verify Registration**
   - Check if the library appears in Context7's library list
   - Test with an MCP client to ensure accessibility

### Method 2: Configuration File (Advanced)

For more control over the registration, use the `context7.json` configuration:

1. **Configuration File Created**
   
   We've already created `/context7.json` with optimal settings:
   ```json
   {
     "projectTitle": "RFS Framework (Reactive Functional Serverless)",
     "packageName": "rfs-framework",
     "repository": "https://github.com/interactord/rfs-framework",
     ...
   }
   ```

2. **Submit via Pull Request**
   - Fork the Context7 registry repository
   - Add RFS Framework configuration
   - Submit a pull request with the configuration

3. **Wait for Approval**
   - Context7 team reviews the submission
   - Once approved, the framework becomes available

## Testing Context7 Integration

### Using Claude Desktop

1. **Install Claude Desktop**
   - Download from: https://claude.ai/download

2. **Configure MCP**
   ```json
   {
     "mcpServers": {
       "context7": {
         "command": "npx",
         "args": ["@context7/mcp-server"]
       }
     }
   }
   ```

3. **Test RFS Framework Access**
   ```
   // In Claude Desktop
   > Can you show me RFS Framework documentation?
   > How do I use Result pattern in RFS Framework?
   ```

### Using MCP Tools

Once registered, the framework can be accessed via MCP tools:

```python
# Using Context7 MCP tools

# 1. Resolve library ID
library_id = resolve_library_id("rfs-framework")
# or
library_id = resolve_library_id("rfs-framework")

# 2. Get documentation
docs = get_library_docs(library_id, "Result pattern")

# 3. Get specific examples
examples = get_library_docs(library_id, "Flux examples")
```

## Verification Checklist

After registration, verify these aspects:

- [ ] **Library Discovery**: Can find "rfs-framework" via `resolve-library-id`
- [ ] **Documentation Access**: Can retrieve docs via `get-library-docs`
- [ ] **Code Examples**: Examples are properly formatted and accessible
- [ ] **Version Information**: Current version (4.0.1) is correctly displayed
- [ ] **API Reference**: Core APIs (Result, Flux, Mono) are documented
- [ ] **Installation Instructions**: `pip install rfs-framework` is prominently shown

## Maintaining Context7 Integration

### Automatic Updates

Context7 automatically syncs with your GitHub repository:
- Documentation updates are fetched periodically
- New releases trigger re-indexing
- No manual intervention needed for updates

### Manual Updates

To force an update or modify settings:

1. **Update `context7.json`** in your repository
2. **Trigger Re-indexing** via Context7 dashboard (if available)
3. **Version Bumps** automatically trigger updates

### Best Practices

1. **Keep Documentation Current**
   - Update README.md with each release
   - Maintain API_REFERENCE.md accuracy
   - Include practical examples

2. **Use Clear Structure**
   - Organize docs in standard locations
   - Use consistent formatting
   - Include code examples

3. **Version Management**
   - Tag releases properly
   - Update version in `pyproject.toml`
   - Document breaking changes

4. **Language Support**
   - Primary docs in English for wider reach
   - Include multilingual docs if needed
   - Use clear, technical language

## Troubleshooting

### Library Not Found

If Context7 can't find the library:
- Verify registration was completed
- Check repository is public
- Ensure documentation files exist
- Wait 24 hours for indexing

### Outdated Documentation

If docs appear outdated:
- Check GitHub repository has latest changes
- Verify Context7 has repository access
- Trigger manual re-index if available
- Contact Context7 support

### Missing Features

If some features aren't documented:
- Ensure they're in indexed folders
- Add to `context7.json` folders list
- Include in main documentation files
- Use standard docstring formats

## Support

### RFS Framework
- GitHub Issues: https://github.com/interactord/rfs-framework/issues
- Documentation: https://github.com/interactord/rfs-framework

### Context7
- Website: https://context7.com
- Documentation: https://context7.com/docs
- Support: Contact through their website

## Current Status

✅ **context7.json** - Configuration file created and optimized
✅ **English Documentation** - API_EN.md created with comprehensive API reference
✅ **Examples** - Code examples included in configuration
⏳ **Registration** - Ready for submission via web interface
⏳ **Verification** - Pending after registration

## Next Steps

1. **Register via Web Interface**
   - Go to https://context7.com/add-library
   - Submit repository URL
   - Wait for confirmation

2. **Test Integration**
   - Use MCP client to verify access
   - Test documentation retrieval
   - Validate code generation

3. **Monitor Usage**
   - Track how AI assistants use the documentation
   - Gather feedback from users
   - Improve documentation based on usage patterns

---

*Last Updated: January 2024*
*RFS Framework Version: 4.0.1*