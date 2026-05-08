# Project Adaptation Guide

This repository is a master starter, not a finished project.

When cloning into a real project, adapt in this order:

## Step 1: Update CLAUDE.md

Add:
- project stack
- repo conventions
- language preferences
- deployment context
- domain terminology
- review expectations
- routing hints if needed

## Step 2: Add project references

Add files in references/ for:
- architecture notes
- stack-specific rules
- domain concepts
- review checklists
- release practices

## Step 3: Refine agents only if needed

Only refine an agent when:
- the project has strong framework-specific patterns
- the domain is unusual
- the default master agent keeps making the same mistake
- a stricter or more specific review standard is needed

## What should stay in master agents

Keep in master agents:
- role
- scope
- workflow
- decision rules
- checklists
- output format

## What should stay outside master agents

Keep outside master agents:
- framework versions
- repo paths
- stack-specific conventions
- naming rules
- team process details
- domain-specific assumptions