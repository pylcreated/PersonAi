# Legacy compatibility snapshot

这里暂存第二阶段迁移前位于项目根目录的兼容入口。

正式源码只位于 `personal_agent/`，正式启动方式是：

```powershell
.\.venv\Scripts\python.exe -m personal_agent
```

新代码和测试不得导入本目录。确认不再有外部调用方依赖这些兼容模块后，
可以在后续版本整体删除 `legacy/`。
