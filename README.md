# 🛵 Ninebot 九号电动车

<a name="install"></a>
## 安装/更新

#### 方法1: [HACS](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=hasscc&repository=ninebot)

#### 方法2: 通过 Samba / SFTP 手动安装
> [下载](https://github.com/hasscc/ninebot/archive/main.zip)解压并复制`custom_components/ninebot`文件夹到HA配置目录下的`custom_components`文件夹

#### 方法3: 通过`SSH`或`Terminal & SSH`加载项执行一键安装命令
```shell
wget -O - https://get.hacs.vip | DOMAIN=ninebot REPO_PATH=hasscc/ninebot ARCHIVE_TAG=main bash -
```

#### 方法4: `shell_command`服务
1. 复制代码到HA配置文件 `configuration.yaml`
    ```yaml
    shell_command:
      update_ninebot: |-
        wget -O - https://get.hacs.vip | DOMAIN=ninebot REPO_PATH=hasscc/ninebot ARCHIVE_TAG=main bash -
    ```
2. 重启HA使配置生效
3. 在开发者工具中执行服务 [`action: shell_command.update_ninebot`](https://my.home-assistant.io/redirect/developer_call_service/?service=shell_command.update_ninebot)
4. 再次重启HA使插件生效
