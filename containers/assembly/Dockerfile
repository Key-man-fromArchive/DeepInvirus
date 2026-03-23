# @TASK T0.2 - Assembly module container
# @SPEC docs/planning/02-trd.md#2.2-분석-도구
# Container: deepinvirus/assembly:1.0.0
# Tools: MEGAHIT (>=1.2.9), metaSPAdes (>=3.15)

FROM condaforge/mambaforge:latest

LABEL maintainer="DeepInvirus Team"
LABEL description="Assembly module: MEGAHIT + metaSPAdes"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/deepinvirus/deepinvirus"
LABEL tools.megahit.version=">=1.2.9"
LABEL tools.spades.version=">=3.15"

# Install tools via mamba from bioconda
RUN mamba install -y -n base \
        -c bioconda -c conda-forge \
        megahit>=1.2.9 \
        spades>=3.15 \
    && mamba clean -afy \
    && conda clean -afy \
    && find /opt/conda -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/conda -name "*.a" -delete 2>/dev/null || true \
    && find /opt/conda -name "*.pyc" -delete 2>/dev/null || true

# Verify installations
RUN megahit --version 2>&1 && \
    metaspades.py --version 2>&1 || spades.py --version 2>&1

WORKDIR /data

CMD ["bash"]
