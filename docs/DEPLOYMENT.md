# 运行与部署

当前同时提供本地研究原型和腾讯云演示部署：Python标准库HTTP服务、浏览器工作台、SQLite留痕。官方Jev通过外部TypeSafe API调用，不在服务器安装官方模型权重。云端部署用于竞赛演示与受控仿真，不代表工商银行生产接入。

## 云端演示入口

- 普通流程模拟：http://123.207.241.109/
- 官方 Jev 工作台：http://123.207.241.109:8772/

云端入口当前使用 IP 和 HTTP，未配置生产级域名、TLS、统一身份认证或银行网络接入。官方工作台的写入操作需要页面会话令牌；一键填充 D01、D02、D03 仅用于演示材料准备。不要把演示环境提交结果解释为工行业务效果。

## 无模型流程演示

在仓库根目录执行：

```powershell
python -X utf8 demo/app.py --mode simulation --port 8765
```

打开 http://127.0.0.1:8765/ 。流程演示有预设结论，不计模型效果。

## 官方界面只读预览

```powershell
python -X utf8 demo/official_workbench.py --preview --port 8773
```

打开 http://127.0.0.1:8773/ 。该模式不调用官方API，写操作关闭。

## 官方Jev工作台

在本地PowerShell会话中配置自己的`JEV_API_KEY`或`TYPESAFE_API_KEY`后执行：

```powershell
python -X utf8 demo/official_workbench.py --port 8771 --max-requests 20
```

本地地址为 http://127.0.0.1:8771/；云端地址见上节。仅使用自编仿真材料；每个语义任务一次请求，失败转人工、无自动重试。仅配置凭据和打开页面不等于领域实验完成。服务固定校验官方地址及模型身份。

跨机器统一启动入口：

```powershell
.\scripts\start-demo.ps1 -Mode simulation -Port 8765
.\scripts\start-demo.ps1 -Mode official-preview -Port 8773
.\scripts\start-demo.ps1 -Mode official -Port 8771 -MaxRequests 20
```

历史`demo/start*.ps1`部分包含原开发电脑Python路径，迁移时优先使用上面的入口或直接调用Python。

## 社区与双系统实验

社区权重不包含在仓库中，需分别下载并按模型卡许可使用。参考本机已验证的依赖版本：

```powershell
python -m pip install -r requirements-model.txt
python demo/download_model.py
python demo/download_slow_model.py
python -X utf8 demo/app.py --mode shadow --port 8767
```

本地双系统使用`--mode dual`，慢分析为Qwen替代模型，不是工银智涌。模型文件hash由加载代码检查，CPU启动可能耗时较长。

## 离线软件检查

```powershell
python -m pip install -r requirements-test.txt
python -X utf8 -m unittest discover -s demo -p 'test_*.py' -v
python -X utf8 -m unittest discover -s 评审整改/PM21_官方Jev业务接入与同任务对照 -p 'test_*.py' -v
python scripts/check-release.py
```

软件测试不调用收费服务，不估计银行领域准确率。官方同任务批次仅在明确需要新实测时从已配置会话运行既有入口；已有run先检查，不重复收费。

## 银行适配

行内接入需要确认材料授权、字段与口径、人员身份、接口权限、审计保存与模型采用门禁。先离线同任务比较，再决定有限辅助使用。GitHub发布和本地接口检查均不视为银行环境验收。
