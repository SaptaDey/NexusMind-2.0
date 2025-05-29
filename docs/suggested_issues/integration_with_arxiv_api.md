**Title:** Feature Request: Integration with Arxiv API for Evidence Gathering

**Is your feature request related to a problem? Please describe.**
The evidence gathering stage could be enhanced by directly sourcing information from pre-print archives like Arxiv.

**Describe the solution you'd like**
Integrate the Arxiv API (or a suitable Python wrapper) into the evidence gathering stage(s).
This would allow NexusMind to:
- Search Arxiv for relevant papers based on hypotheses or query dimensions.
- Potentially extract abstracts or full text (if available and permissible) to be used as evidence.
- Create nodes and relationships in the graph representing Arxiv findings.

**Describe alternatives you've considered**
Manual searching and input of Arxiv findings. Relying solely on existing knowledge or other configured data sources.

**Additional context**
This could broaden the scope of automated evidence collection and keep NexusMind updated with cutting-edge research.
Considerations:
- API rate limits and terms of use.
- Processing and relevance filtering of Arxiv search results.
- How to represent Arxiv data in the graph model.
