# 使用基础镜像
# Start of Selection
FROM ubuntu:20.04
# End of Selection
ENV DEBIAN_FRONTEND=noninteractive
# 安装构建 Python 所需的依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libffi-dev \
    zlib1g-dev \
    wget \
    curl \
    llvm \
    libgdbm-dev \
    liblzma-dev \
    tk-dev \
    && apt-get clean

# 设置工作目录
WORKDIR /usr/src

# 下载 Python 源代码
RUN wget https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tgz && \
    tar xzf Python-3.13.0.tgz

# 构建和安装 Python
WORKDIR /usr/src/Python-3.13.0
RUN ./configure --disable-gil && \
    make && \
    make install

# 清理
RUN rm -f /usr/src/Python-3.13.0.tgz && \
    rm -rf /usr/src/Python-3.13.0

# 设置 PATH
ENV PATH="/usr/local/bin:${PATH}"

# 复制应用程序代码
COPY ./requirements.txt /app/requirements.txt

# 设置工作目录
WORKDIR /app

ENV PYTHONPATH=/app

# 安装 Python 依赖
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# 运行 Python 程序
CMD ["python3"]