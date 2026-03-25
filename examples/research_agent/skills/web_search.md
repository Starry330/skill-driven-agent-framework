---
name: web_search
description: Search the web for information.
parameters:
  type: object
  properties:
    query:
      type: string
      description: The search query.
  required:
    - query
metadata:
  category: research
---
Use the web_search tool to find information about the given query.
Provide the query as a string.
The output will be a list of search results.
