# 打包说明

本文档说明如何使用 PyInstaller 将 Mexico Instagram Creator Finder 打包为 Windows 独立应用。

## 一、打包模式

当前使用 **目录模式**（`--noonefile`，PyInstaller 6.x 默认）。

目录模式的优势：

- 排查缺失依赖方便（`_internal/` 目录可见）
- 携带 YAML 配置（`config/` 目录可直接修改）
- 携带静态资源（NiceGUI 前端文件）
- 增量更新本地文件更快（无需每次重新解压）
- 启动速度快于单文件模式

完成稳定后再研究 `--onefile` 单文件打包。

## 二、前置要求

### 1. 环境

- Windows 10 / 11 64 位
- Python 3.11+（开发环境实际使用 3.14）
- 项目依赖已安装：`pip install -e .[dev]`

### 2. 关键依赖

- `pyinstaller>=6.0,<7`（已加入 `[project.optional-dependencies].dev`）
- `nicegui>=2.0.0,<3`
- `instagrapi>=2.18.8,<3`
- `pillow`（用于生成图标，仅打包时需要）

### 3. 安装打包依赖

```powershell
cd "d:\桌面\ins\instagrapi\mexico-instagram-creator-finder"
pip install -e ".[dev]"
```

## 三、生成应用图标

项目已内置图标生成脚本，运行后会生成 `assets/app.ico` 与 `assets/app.png`：

```powershell
python scripts/make_icon.py
```

输出：

```text
icon saved: .../assets/app.ico
preview: .../assets/app.png
```

如需自定义图标，替换 `assets/app.ico` 后重新打包即可。

## 四、执行打包

### 一键打包命令

```powershell
cd "d:\桌面\ins\instagrapi\mexico-instagram-creator-finder"
pyinstaller --noconfirm MexicoCreatorFinder.spec
```

### 输出目录结构

打包完成后 `dist/MexicoCreatorFinder/` 包含：

```text
dist/MexicoCreatorFinder/
├─ MexicoCreatorFinder.exe        主程序
├─ config/                        YAML 配置（可修改覆盖）
│  ├─ default.yaml
│  ├─ hashtags.yaml
│  ├─ mexico_locations.yaml
│  ├─ niche_keywords.yaml
│  └─ excluded_account_terms.yaml
├─ .env.example                   凭据示例文件
├─ README.md
├─ LICENSE
├─ THIRD_PARTY_NOTICES.md
├─ data/                          SQLite 数据库运行时创建于此
├─ output/                        导出文件运行时创建于此
├─ logs/                          日志运行时创建于此
└─ _internal/                     Python 运行时 + 全部依赖（请勿修改）
   ├─ nicegui/                    NiceGUI 前端静态资源
   ├─ config/                     配置回退副本（_internal/config 中）
   ├─ *.dll                       Windows 运行时 DLL
   └─ ...
```

### 用户使用流程

1. 复制整个 `dist/MexicoCreatorFinder/` 目录到目标机器（绿色软件，无需安装）
2. 在 exe 同级目录创建 `.env` 文件，填写 Instagram 凭据：

   ```text
   IG_USERNAME=your_instagram_username
   IG_PASSWORD=your_instagram_password
   ```

3. 双击 `MexicoCreatorFinder.exe` 启动
4. 浏览器自动打开 <http://127.0.0.1:8080>（如未自动打开，手动访问）

## 五、Spec 文件说明

`MexicoCreatorFinder.spec` 关键配置：

### 1. 数据文件收集

```python
datas = []
datas += collect_data_files("nicegui")   # NiceGUI 静态资源（JS/CSS/模板）
datas += collect_data_files("vbuild")    # vbuild 资源
```

### 2. 隐藏导入

```python
hiddenimports = []
hiddenimports += collect_submodules("nicegui")
hiddenimports += collect_submodules("vbuild")
hiddenimports += collect_submodules("instagrapi")
hiddenimports += collect_submodules("openpyxl")
# 项目内部所有模块显式列出
hiddenimports += ["app.cli", "app.config", "app.gui.pages.new_search", ...]
```

### 3. 排除项（减小体积）

```python
excludes = ["tests", "pytest", "ruff", "pyinstaller", "PIL"]
```

### 4. config 目录处理

```python
coll = COLLECT(
    exe, a.binaries, a.datas,
    Tree(str(PROJECT_ROOT / "config"), prefix="config"),  # 复制到 _internal/config
    name="MexicoCreatorFinder",
)
```

post-build 阶段还会把 `config/` 复制到 exe 同级目录，便于用户修改。

### 5. EXE 选项

```python
console=False,        # --windowed 模式，无控制台窗口
upx=False,            # 不使用 UPX 压缩，避免被杀软误杀
icon="assets/app.ico",
```

## 六、路径解析（开发环境 vs 打包环境）

`app/config.py` 已处理两种环境的路径解析：

```python
def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller 打包后
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def _resolve_config_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        user_config = exe_dir / "config"
        if user_config.exists():
            return user_config              # 优先用 exe 同级的 config
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "config" # 回退到 _internal/config
    return _resolve_project_root() / "config"
```

`.env` 文件解析也类似：打包后从 `exe 同级/.env` 读取，开发环境从项目根目录读取。

## 七、Python 3.14 兼容性

`vbuild 0.8.2`（NiceGUI 依赖）使用了 Python 3.14 已移除的 `pkgutil.find_loader`。`gui_main.py` 顶部已添加 shim：

```python
import importlib.util
import pkgutil

if not hasattr(pkgutil, "find_loader"):
    def _find_loader(full_name: str):
        try:
            spec = importlib.util.find_spec(full_name)
            return spec.loader if spec is not None else None
        except (ImportError, AttributeError, ValueError):
            return None
    pkgutil.find_loader = _find_loader
```

此补丁必须在 `import nicegui` 之前执行。

## 八、常见问题

### Q1: 启动后浏览器无法访问 8080？

- 检查防火墙是否阻止（本地访问通常无问题）
- 检查 8080 端口是否被占用：`netstat -ano | findstr ":8080"`
- 如端口被占用，修改 `gui_main.py` 中的 `port=8080` 重新打包

### Q2: 双击 exe 闪退？

`--windowed` 模式下无错误输出。改为 console 模式重新打包查看错误：

```python
# 临时修改 MexicoCreatorFinder.spec
exe = EXE(..., console=True, ...)
```

重新打包后双击，控制台会显示错误信息。

### Q3: 杀毒软件误报？

- 不使用 UPX 压缩（已在 spec 中 `upx=False`）
- 可向杀软厂商提交白名单申请
- 或使用代码签名证书对 exe 进行签名

### Q4: 打包后体积过大？

当前约 500MB+，主要来自：

- NiceGUI 依赖链（matplotlib、scipy、pandas）
- instagrapi 依赖链（cryptography、pydantic）
- Python 3.14 运行时

减小体积方案：

- 在 spec 的 `excludes` 中排除不需要的模块（如 `matplotlib.backends`）
- 使用 Nuitka 替代 PyInstaller（更激进的死代码消除）
- 等待 NiceGUI 3.x 精简依赖

### Q5: 修改了 config/*.yaml 后如何生效？

- 直接修改 `dist/MexicoCreatorFinder/config/*.yaml`
- 重启 exe 即可生效（无需重新打包）
- 代码会优先读取 exe 同级 `config/`，覆盖 `_internal/config/`

### Q6: 如何升级到 --onefile 单文件模式？

待目录模式稳定后：

1. 修改 spec：将 `EXE(..., exclude_binaries=True)` 改为 `exclude_binaries=False`
2. 删除 `COLLECT(...)` 块
3. 重新打包

注意：单文件模式启动较慢（每次需解压到临时目录），且首次启动可能被 Windows Defender 扫描延迟。

## 九、清理与重打包

```powershell
# 清理上次构建产物
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# 重新打包
pyinstaller --noconfirm MexicoCreatorFinder.spec
```

## 十、验证打包结果

打包后应执行以下验证：

1. **启动测试**：双击 `MexicoCreatorFinder.exe`，浏览器访问 <http://127.0.0.1:8080>
2. **配置加载**：「新建搜索」页面 Hashtag 列表应自动填充（说明 `config/hashtags.yaml` 解析正常）
3. **页面切换**：6 个导航按钮（新建搜索 / 任务进度 / 搜索结果 / 排除名单 / 导出 / 设置）都能正常切换
4. **设置页**：「Instagram 凭据」区域应显示 IG_USERNAME / IG_PASSWORD 输入框
5. **DRY-RUN 搜索**：勾选 DRY-RUN → 启动搜索 → 切换到「任务进度」页观察 → 完成后到「搜索结果」查看
6. **导出测试**：「导出」页面选择任务 → 选择 CSV/JSON/XLSX → 点击导出 → 验证 `output/` 目录生成文件
7. **路径测试**：将整个 `dist/MexicoCreatorFinder/` 复制到其他目录（如 `D:\test\`）后再次启动，确认仍能正常工作

## 十一、分发注意事项

- **不要打包 `.env` 文件**：用户应自行创建并填写凭据
- **保留 `THIRD_PARTY_NOTICES.md`**：本项目使用 instagrapi（MIT License），需保留第三方声明
- **不修改 `LICENSE`**：本项目遵循 MIT License
- **不包含 Instagram Session 文件**：`.instagram_session.json` 由用户首次登录后生成
- **不包含 SQLite 数据库**：`data/app.db` 由用户运行时创建

## 十二、参考

- PyInstaller 官方文档：<https://pyinstaller.org/>
- NiceGUI 打包指南：<https://nicegui.io/documentation/section_deploy#deployment_as_an_executable>
- Python 3.14 移除的 API：<https://docs.python.org/3.14/whatsnew/3.14.html>
