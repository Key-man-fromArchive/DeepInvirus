# @TASK T0.2 - Reporting module container
# Container: deepinvirus/reporting:1.0.0
# Tools: Python 3.11 + visualization/reporting/multiqc

FROM condaforge/mambaforge:latest

LABEL maintainer="DeepInvirus Team"
LABEL description="Reporting module: Python visualization + report generation + MultiQC"
LABEL version="1.0.0"

# Install all in one mamba call to avoid conflicts
RUN mamba install -y -n base \
        -c bioconda -c conda-forge \
        python=3.11 \
        pandas \
        numpy \
        scipy \
        scikit-bio \
        matplotlib \
        seaborn \
        plotly \
        jinja2 \
        multiqc \
    && pip install --no-cache-dir \
        python-docx \
    && mamba clean -afy \
    && conda clean -afy \
    && find /opt/conda -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/conda -name "*.a" -delete 2>/dev/null || true

# Verify key tools
RUN python --version && multiqc --version && python -c "import docx; print('python-docx OK')"

WORKDIR /data
CMD ["bash"]
