# @TASK T0.2 - Reporting module container
# @SPEC docs/planning/02-trd.md#2.3-보고서/시각화
# Container: deepinvirus/reporting:1.0.0
# Tools: Python 3.11 + visualization/reporting libraries

FROM condaforge/mambaforge:latest

LABEL maintainer="DeepInvirus Team"
LABEL description="Reporting module: Python visualization + report generation"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/deepinvirus/deepinvirus"
LABEL tools.python.version="3.11"

# Install Python 3.11 and all required libraries
RUN mamba install -y -n base \
        -c conda-forge \
        python=3.11 \
        pandas>=2.0 \
        numpy>=1.24 \
        scipy>=1.11 \
        scikit-bio>=0.6 \
        matplotlib>=3.8 \
        seaborn>=0.13 \
        plotly>=5.18 \
        jinja2>=3.1 \
    && pip install --no-cache-dir \
        python-docx>=1.1 \
    && mamba clean -afy \
    && conda clean -afy \
    && pip cache purge 2>/dev/null || true \
    && find /opt/conda -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/conda -name "*.a" -delete 2>/dev/null || true \
    && find /opt/conda -name "*.pyc" -delete 2>/dev/null || true

# Verify installations
RUN python --version && \
    python -c "import pandas; print(f'pandas {pandas.__version__}')" && \
    python -c "import numpy; print(f'numpy {numpy.__version__}')" && \
    python -c "import matplotlib; print(f'matplotlib {matplotlib.__version__}')" && \
    python -c "import seaborn; print(f'seaborn {seaborn.__version__}')" && \
    python -c "import plotly; print(f'plotly {plotly.__version__}')" && \
    python -c "import docx; print('python-docx OK')" && \
    python -c "import scipy; print(f'scipy {scipy.__version__}')" && \
    python -c "import skbio; print(f'scikit-bio {skbio.__version__}')" && \
    python -c "import jinja2; print(f'jinja2 {jinja2.__version__}')"

WORKDIR /data

CMD ["bash"]
