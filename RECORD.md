# 实验效果记录

## 测试环境

系统: Ubuntu 22.04.2 LTS

CPU: 13th Gen Intel(R) Core(TM) i9-13900K

内存: 32GB

文件描述符:

- `ulimit -u` : 127740
- `ulimit -n` : 1048576

## 系统1

系统描述：一个服务仅包含一个socket，无连接缓存

## 系统2

### 系统描述

一个服务仅包含一个socket，有连接缓存

### 参数设置

| 名称                        | 设置             | 备注                                                                             |
| --------------------------- | ---------------- | -------------------------------------------------------------------------------- |
| NUM_API_SERVICES            | 20               | 启动服务的数量，每个服务运行在一个独立的进程中                                   |
| NUM_WORKERS_PER_API_SERVICE | 25               | 每个服务中的线程池大小，线程池用来处理收到的请求，<br />每个线程处理一个请求     |
| NUM_CLIENTS                 | NUM_API_SERVICES | 客户端的数量，一般和服务的数量保持一致                                           |
| NUM_REQUESTS_PER_CLIENT     | 1000             | 每个客户端向每个服务发送的请求数量                                               |
| NUM_THREADS_PER_CLIENT      | 25               | 每个客户端的线程池大小，线程池用来向服务端发送请求，<br />每个线程负责一个服务端 |
| CALC_TARGET                 | 1000             | 服务端应用要计算的数字大小（影响服务端每个请求的CPU计算负载）                    |

### 测试结果

每个客户端发送完所有请求的耗时

复用连接: `reuse_client=True`

python-gil: 带有全局解释锁的Python 3.11.5

python-nogil: 不带全局解释锁的Python 3.14.0a0 experimental free-threading build

| 类型                           | 耗时  |
| ------------------------------ | ----- |
| 客户端复用连接，python-gil     | 5.5s  |
| 客户端不复用连接，python-gil   | 14.9s |
| 客户端复用连接，python-nogil   | 5.0s  |
| 客户端不复用连接，python-nogil | 10.3  |

## 系统3

### 系统描述

Tornado服务

### 参数设置

| 名称                    | 设置             | 备注                                                                             |
| ----------------------- | ---------------- | -------------------------------------------------------------------------------- |
| NUM_API_SERVICES        | 20               | 启动服务的数量，每个服务运行在一个独立的进程中                                   |
| NUM_CLIENTS             | NUM_API_SERVICES | 客户端的数量，一般和服务的数量保持一致                                           |
| NUM_REQUESTS_PER_CLIENT | 1000             | 每个客户端向每个服务发送的请求数量                                               |
| NUM_THREADS_PER_CLIENT  | 25               | 每个客户端的线程池大小，线程池用来向服务端发送请求，<br />每个线程负责一个服务端 |
| CALC_TARGET             | 1000             | 服务端应用要计算的数字大小（影响服务端每个请求的CPU计算负载）                    |

### 测试结果

| 类型         | 耗时                |
| ------------ | ------------------- |
| python-gil   | 16.1s               |
| python-nogil | 17.2s😂（还更慢了） |

## 系统4

### 系统描述

每个server可以监听多个socket，共用一套连接缓存（使用一个线程池）

### 参数设置

| 名称                    | 设置             | 备注                                                                             |
| ----------------------- | ---------------- | -------------------------------------------------------------------------------- |
| NUM_API_SERVICES        | 20               | 启动服务的数量，每个服务运行在一个独立的进程中                                   |
| NUM_MULTI_SOCKET        | 10               | 每个server监听的socket数量                                                       |
| NUM_MAX_CONNS           | None             | 每个server缓存连接的数量, None代表不限制                                         |
| NUM_CLIENTS             | NUM_API_SERVICES | 客户端的数量，一般和服务的数量保持一致                                           |
| NUM_REQUESTS_PER_CLIENT | 1000             | 每个客户端向每个服务发送的请求数量                                               |
| NUM_THREADS_PER_CLIENT  | 25               | 每个客户端的线程池大小，线程池用来向服务端发送请求，<br />每个线程负责一个服务端 |
| CALC_TARGET             | 1000             | 服务端应用要计算的数字大小（影响服务端每个请求的CPU计算负载）                    |

### 测试结果

| 类型                 | 耗时  |
| -------------------- | ----- |
| 对所有连接使用select | 3.03s |
| 对单个连接使用select | 5.57s |

在对所有连接使用select的情况下, 改变NUM_MULTI_SOCKET的值, 观察耗时变化

| 类型                  | 耗时  |
| --------------------- | ----- |
| NUM_MULTI_SOCKET = 1  | 2.35s |
| NUM_MULTI_SOCKET = 5  | 2.60s |
| NUM_MULTI_SOCKET = 10 | 3.03s |

在对单个连接使用select的情况下, 每个客户端只绑定一个连接, 改变NUM_MULTI_SOCKET的值, 观察耗时变化

| 类型                  | 耗时  |
| --------------------- | ----- |
| NUM_MULTI_SOCKET = 1  | 2.44s |
| NUM_MULTI_SOCKET = 5  | 2.47s |
| NUM_MULTI_SOCKET = 10 | 2.60s |

# 系统2的内存占用分析

| 名称                    | 设置             | 备注                                                                             |
| ----------------------- | ---------------- | -------------------------------------------------------------------------------- |
| NUM_API_SERVICES        | 1               | 启动服务的数量，每个服务运行在一个独立的进程中                                   |
| NUM_MULTI_SOCKET        | 1               | 每个server监听的socket数量                                                       |
| NUM_WORKERS_PER_API_SERVICE | 25               | 每个服务中的线程池大小，线程池用来处理收到的请求，<br />每个线程处理一个请求     |
| NUM_MAX_CONNS           | 10000             | 每个server缓存连接的数量, None代表不限制                                         |
| NUM_CLIENTS             | 自变量 | 客户端的数量，一般和服务的数量保持一致                                           |
| NUM_REQUESTS_PER_CLIENT | 500             | 每个客户端向每个服务发送的请求数量                                               |
| NUM_THREADS_PER_CLIENT  | 25               | 每个客户端的线程池大小，线程池用来向服务端发送请求，<br />每个线程负责一个服务端 |
| CALC_TARGET             | 1000             | 服务端应用要计算的数字大小（影响服务端每个请求的CPU计算负载）                    |

发送数据
```python
data = {'target': CALC_TARGET, 'text': 'hello world'*10000}
```

结果
| NUM_CLIENTS                  | 内存占用(MB)  |
| --------------------- | ----- |
| 0  | 1837.1  |
| 200  | 4263.0  |
| 400  | 6426.8 |
| 600 | 8657.5 |
| 800 | 10872.0 |
| 1000 | 13240.0 |

发送数据
```python
data = {'target': CALC_TARGET, 'text': 'hello world'}
```

结果
| NUM_CLIENTS                  | 内存占用(MB)  |
| --------------------- | ----- |
| 0  | 1837.1  |
| 200  | 4118.9 |
| 400  | 6275.2 |
| 600  | 8422.2 |

结论:
- 内存占用和发送的数据量无关
- 内存占用和客户端数量成正比, 每 200 个客户端增加 2GB 左右的内存占用

如果使用基于docker的python来执行程序, 内存占用较高; 如果使用本地python来执行程序, 内存占用较低, 当 NUM_CLIENTS 为 200 时, 内存占用为 3256MB 左右
