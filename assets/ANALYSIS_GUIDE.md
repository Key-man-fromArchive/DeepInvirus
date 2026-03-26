# DeepInvirus Analysis Guide

## How to Read Your Results

### 1. Start Here: report.docx
Open `report.docx` in Microsoft Word. The Table of Contents on page 1 links to all sections.
Update the TOC: right-click -> "Update Field" -> "Update entire table".

### 2. Interactive Exploration: dashboard.html
Open `dashboard.html` in a web browser. Tabs:
- **Overview**: Summary statistics and key metrics
- **Composition**: Taxonomic composition visualization
- **Coverage**: Per-sample viral contig coverage heatmap
- **Diversity**: Alpha/beta diversity (if n>=3 samples)
- **Search**: Filter and search all detected viruses
- **Results**: Publication-quality figures (inline images)

### 3. Raw Data: taxonomy/bigtable.tsv
The master results table. Open in Excel or R/Python for custom analysis.
Key columns: seq_id, sample, family, coverage, breadth, detection_confidence, rpm

### 4. Diversity: diversity/
- `alpha_diversity.tsv`: Per-sample Shannon, Simpson, Chao1, Pielou evenness
- `beta_diversity.tsv`: Bray-Curtis pairwise distance matrix
- `pcoa_coordinates.tsv`: PCoA ordination coordinates for plotting

### 5. QC: qc/
- `multiqc_report.html`: Aggregate quality control report
- Individual BBDuk and host removal statistics

### 6. Figures: figures/
PNG (300 DPI) and SVG (vector) versions of all analysis figures.
Use SVG files for journal submission.

## Interpreting Key Results

### Detection Confidence Tiers
| Tier | Criteria | Interpretation |
|------|----------|----------------|
| **high** | breadth >= 70%, depth >= 10x | Strong evidence of virus presence |
| **medium** | breadth >= 30%, depth >= 1x | Moderate evidence, may need validation |
| **low** | below medium thresholds | Weak evidence, possible artifact |

### What "Unclassified" Means
Contigs classified as "Unclassified" lack a family-level taxonomic assignment ending in *-viridae*. They may be:
- Novel viruses not yet in reference databases
- Highly divergent sequences with weak homology
- Non-viral sequences misidentified by detection tools

### RNA-seq Caveat for DNA Viruses
If your input is RNA-seq data, detection of DNA viruses (e.g., Parvoviridae, Baculoviridae) reflects **viral transcription**, not genome abundance. High coverage means active transcription, which is consistent with but not proof of active replication.

## Next Steps
1. Validate key findings with PCR or targeted sequencing
2. Compare with Kraken2/read-based classification if available
3. For novel viruses: perform phylogenetic analysis of marker genes (RdRp, MCP)
4. For publication: use SVG figures from figures/ directory
