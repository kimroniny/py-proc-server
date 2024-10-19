# py-proc-server
server/client communication between processes in python

## python3-nogil镜像

介绍如何使用无 GIL 锁的 python 版本来执行脚本, 这里使用`docker`构建`python_3_13_nogil`镜像, 并运行脚本

### docker设置代理

以下方法针对 `docker build` 命令

```
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo vim /etc/systemd/system/docker.service.d/http-proxy.conf
```

下面的代理地址需要修改为当前代理地址
```
[Service]
Environment="HTTP_PROXY=http://10.210.136.63:7890"
Environment="HTTPS_PROXY=http://10.210.136.63:7890"
```

重启docker使配置生效

```
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 构建镜像

```
docker build . -t python_3_13_nogil:latest
```

### 运行

命令已经写入`docker_python3`文件, 直接调用即可
```
./docker_python3 script.py --arg1 value1 --arg2 value2
```

