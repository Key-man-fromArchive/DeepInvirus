# @TASK T0.2 - QC module container
# @SPEC docs/planning/02-trd.md#2.2-분석-도구
# Container: deepinvirus/qc:1.0.0
# Tools: fastp (>=0.23), minimap2 (>=2.26), samtools (>=1.18), bbmap (>=39.0)

FROM condaforge/mambaforge:latest

LABEL maintainer="DeepInvirus Team"
LABEL description="QC module: fastp + bbmap (bbduk) + minimap2 + samtools"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/deepinvirus/deepinvirus"
LABEL tools.fastp.version=">=0.23"
LABEL tools.bbmap.version=">=39.0"
LABEL tools.minimap2.version=">=2.26"
LABEL tools.samtools.version=">=1.18"

# Install tools via mamba from bioconda
RUN mamba install -y -n base \
        -c bioconda -c conda-forge \
        fastp>=0.23 \
        bbmap>=39.0 \
        minimap2>=2.26 \
        samtools>=1.18 \
    && mamba clean -afy \
    && conda clean -afy \
    && find /opt/conda -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/conda -name "*.a" -delete 2>/dev/null || true \
    && find /opt/conda -name "*.pyc" -delete 2>/dev/null || true

# Verify installations
RUN fastp --version 2>&1 && \
    bbduk.sh --version 2>&1 || true && \
    minimap2 --version && \
    samtools --version | head -n 1

WORKDIR /data

CMD ["bash"]
