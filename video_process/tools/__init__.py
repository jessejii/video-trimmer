# -*- coding: utf-8 -*-
"""业务逻辑层：纯函数，无 print / input，全部通过 ToolContext 回调上报。

每个工具模块暴露统一签名的 run(...) 函数，返回 TaskResult，
由界面在后台线程中调用。
"""
