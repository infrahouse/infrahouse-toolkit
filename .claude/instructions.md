# Project Instructions for Claude Code

## Terraform Coding Standards

**ALWAYS read and follow `.claude/CODING_STANDARD.md` before writing or modifying any Terraform code.**

This file contains critical requirements including:
- Proper use of ternary operators vs logical OR in validation blocks with nullable variables
- Tagging conventions
- Provider requirements
- Module pinning
- IAM policy patterns

Pay special attention to validation blocks - they require ternary operators to avoid null comparison errors.