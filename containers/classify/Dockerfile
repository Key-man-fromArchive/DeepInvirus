# @TASK T0.2 - Classification module container
# @SPEC docs/planning/02-trd.md#2.2-분석-도구
# Container: deepinvirus/classify:1.0.0
# Tools: MMseqs2 (>=15.6), TaxonKit (>=0.15), CoverM (>=0.7)

FROM condaforge/mambaforge:latest

LABEL maintainer="DeepInvirus Team"
LABEL description="Classification module: MMseqs2 + TaxonKit + CoverM"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/deepinvirus/deepinvirus"
LABEL tools.mmseqs2.version=">=15.6"
LABEL tools.taxonkit.version=">=0.15"
LABEL tools.coverm.version=">=0.7"

# Install tools via mamba from bioconda
RUN mamba install -y -n base \
        -c bioconda -c conda-forge \
        mmseqs2>=15.6 \
        taxonkit>=0.15 \
        coverm>=0.7 \
    && mamba clean -afy \
    && conda clean -afy \
    && find /opt/conda -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/conda -name "*.a" -delete 2>/dev/null || true \
    && find /opt/conda -name "*.pyc" -delete 2>/dev/null || true

# Verify installations
RUN mmseqs version 2>&1 && \
    taxonkit version 2>&1 && \
    coverm --version 2>&1

WORKDIR /data

CMD ["bash"]
