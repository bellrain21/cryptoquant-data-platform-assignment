FROM ubuntu:24.04

ARG AIRFLOW_VERSION=2.10.5
ARG AIRFLOW_CONSTRAINTS_URL=https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt

ENV AIRFLOW_HOME=/opt/airflow \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AIRFLOW_PYTHON_HOME=/opt/airflow/python \
    PROJECT_PYTHON_HOME=/opt/project/python \
    PATH="/opt/project/python/bin:/opt/airflow/python/bin:${PATH}" \
    PYTHONPATH=/opt/airflow/src \
    DBT_BIN=/opt/project/python/bin/dbt

# Ubuntu 24.04 LTS의 기본 Python 3.12 위에 Airflow와 프로젝트 도구를 설치한다.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        git \
        libpq-dev \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 50000 --gid 0 --home-dir "${AIRFLOW_HOME}" --create-home airflow \
    && mkdir -p "${AIRFLOW_HOME}/dags" "${AIRFLOW_HOME}/logs" "${AIRFLOW_HOME}/plugins" "${AIRFLOW_HOME}/data" \
    && mkdir -p /opt/project \
    && chown -R airflow:0 "${AIRFLOW_HOME}" /opt/project \
    && chmod -R g+rwX "${AIRFLOW_HOME}" /opt/project

COPY requirements-runtime.txt /tmp/requirements-runtime.txt
COPY requirements.txt /tmp/requirements.txt

# Airflow 2.10.x와 dbt 1.9+는 protobuf 범위가 충돌하므로 Python 실행 경로를 분리한다.
RUN python3 -m venv "${AIRFLOW_PYTHON_HOME}" \
    && "${AIRFLOW_PYTHON_HOME}/bin/python" -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && "${AIRFLOW_PYTHON_HOME}/bin/python" -m pip install --no-cache-dir \
        "apache-airflow[postgres]==${AIRFLOW_VERSION}" \
        --constraint "${AIRFLOW_CONSTRAINTS_URL}" \
    && "${AIRFLOW_PYTHON_HOME}/bin/python" -m pip install --no-cache-dir -r /tmp/requirements-runtime.txt \
    && "${AIRFLOW_PYTHON_HOME}/bin/python" -m pip check

RUN python3 -m venv "${PROJECT_PYTHON_HOME}" \
    && "${PROJECT_PYTHON_HOME}/bin/python" -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && "${PROJECT_PYTHON_HOME}/bin/python" -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && "${PROJECT_PYTHON_HOME}/bin/python" -m pip check

WORKDIR ${AIRFLOW_HOME}

USER airflow

CMD ["/bin/bash", "-lc", "airflow version && sleep infinity"]
