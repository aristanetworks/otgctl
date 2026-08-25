# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `$OTG_INSECURE` environment variable for command-line `-k`
- `--timeout` option for HTTP requests, defaulting to 30 seconds
- Test coverage for CLI request options, request execution errors, and invalid
  JSON response fallback
- Pytest source-tree import setup so tests use the checkout under `src/`
- Clean Docker wheel-build test for validating the installed package

### Changed
- Use proper syntax for license in pyproject.toml
- Downgrade dependencies to those available in EOS
- Added --version
- Exit with status 1 for non-2xx HTTP responses
- Report unknown methods before checking whether an input source is required
- Simplify CLI error output for common HTTP transport failures
- Report malformed YAML and embedded methods as CLI errors instead of tracebacks
- Validate API-path keys and segments, and recognize structured JSON responses
- Use PEP 621 project metadata with a setuptools 61+ build requirement,
  compatible with the setuptools 69 toolchain available in EOS

## [0.9.0] - 2026-06-16

### Added
- CLI tool for making OTG REST API calls from YAML, JSON, or API path input
- Support for gRPC method names, REST operation IDs, and REST paths
- Multi-document YAML input for replaying RPC logs
- API path notation (`//path/key=value`) for quick requests
- YAML and JSON output formats
- mTLS client certificate support
- Verbose mode for request/response debugging
