# @TASK T0.2 - Detection module container
# @SPEC docs/planning/02-trd.md#2.2-분석-도구
# Container: deepinvirus/detect:1.0.0
# Tools: geNomad (>=1.7), Diamond (>=2.1)

FROM condaforge/mambaforge:latest

LABEL maintainer="DeepInvirus Team"
LABEL description="Detection module: geNomad + Diamond"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/deepinvirus/deepinvirus"
LABEL tools.genomad.version=">=1.7"
LABEL tools.diamond.version=">=2.1"

# Install tools via mamba from bioconda
RUN mamba install -y -n base \
        -c bioconda -c conda-forge \
        genomad>=1.7 \
        diamond>=2.1 \
    && mamba clean -afy \
    && conda clean -afy \
    && find /opt/conda -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/conda -name "*.a" -delete 2>/dev/null || true \
    && find /opt/conda -name "*.pyc" -delete 2>/dev/null || true

# Verify installations
RUN genomad --version 2>&1 && \
    diamond version 2>&1

WORKDIR /data

CMD ["bash"]
