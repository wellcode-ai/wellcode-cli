# Debugging Guide

## Common Issues and Solutions

### Installation Issues

#### Package Not Found
```bash
pip install wellcode-cli fails with "Package not found"
```
**Solution:**
- Verify you're using Python 3.8 or higher
- Check your pip version: `pip --version`
- Try upgrading pip: `python -m pip install --upgrade pip`

#### Permission Errors
```bash
Permission denied when installing package
```
**Solution:**
- Use a virtual environment
- Or install with user flag: `pip install --user wellcode-cli`

### Configuration Issues

#### GitHub Authentication
```
Error: Could not authenticate with GitHub
```
**Solution:**
1. Verify your GitHub App installation
2. Run `wellcode-cli config` again
3. Check organization permissions

#### API Key Issues
```
Error: Invalid API key
```
**Solution:**
1. Verify API keys in `~/.wellcode/config.json`
2. Regenerate API keys if necessary
3. Run `wellcode-cli config` to reconfigure

### Runtime Issues

#### High Memory Usage
If the CLI is using too much memory:
1. Reduce date range in analysis
2. Use `--limit` option if available
3. Check for memory leaks in custom scripts

#### Slow Performance
If commands are running slowly:
1. Enable debug logging: `export WELLCODE_DEBUG=1`
2. Check network connectivity
3. Verify API rate limits

## Debug Mode

Enable debug logging:
```bash
export WELLCODE_DEBUG=1
wellcode-cli review
```

Debug log location:
- Unix: `~/.wellcode/debug.log`
- Windows: `%USERPROFILE%\.wellcode\debug.log`

## Getting Support

If you can't resolve an issue:

1. Enable debug mode
2. Reproduce the issue
3. Collect logs
4. Create a GitHub issue with:
   - Steps to reproduce
   - Debug logs
   - Environment info
   - Expected vs actual behavior

## Environment Information

Collect system information:
```bash
wellcode-cli debug
```

This provides:
- Python version
- OS details
- Package versions
- Configuration status

## Contributing Debug Improvements

Found a common issue? Help others:
1. Document the solution
2. Add to this guide
3. Submit a PR