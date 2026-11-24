# 发布清单

状态（2026-11-25）：包已建好、9 个测试通过、wheel 已产出、git 已初始化。
**唯一缺的是凭据** —— 这台机器上没有 GitHub token、没有 SSH key、没有 PyPI token。

产出的 wheel：`dist/cairnmem-0.1.0-py3-none-any.whl`（约 25 KB，零依赖）

---

## 方式一：GitHub（推荐，先发这里）

需要一样东西：一个 **Personal Access Token**（有 `repo` 权限），或一对 SSH key。

`@bash
cd cairnmem
git remote add origin https://github.com/<你的账号>/cairnmem.git
git branch -M main
git push -u origin main
`@

推之前先在网页上建一个空仓库（不要勾 README / .gitignore，否则会冲突）。

## 方式二：PyPI

需要一个 **API token**（pypi.org -> Account settings -> API tokens）。

`@bash
cd cairnmem
py -3 -m pip install -U build twine
py -3 -m build
py -3 -m twine upload dist/*
# 用户名填 __token__，密码填 pypi-xxxxxx
`@

同名包 `@cairnmem`@ 目前在 PyPI 上**还没被占用**（2026-11-25 查过）。

## 方式三：不发，先自用

`@bash
py -3 -m pip install --no-deps ./dist/cairnmem-0.1.0-py3-none-any.whl
cairn --version
`@

## 发布前还要做

- [ ] 改 `pyproject.toml` 里的 `[project.urls]`（仓库地址、主页）
- [ ] 若要署名，改 `LICENSE` 里的 copyright 行
- [ ] 版本号从 0.1.0 起，之后按 `CHANGELOG` 走
- [ ] 确认 `README.md` 里的数字仍然成立（R@3 0.89 是在一份私有库上测的）

## 不建议公开的东西

这份包里**没有**任何个人数据：没有真实路径、没有会话内容、没有项目名。
停用词表是 MIT 许可的第三方数据，已附来源。

但注意：`cairn.json` 是**本地配置**，会包含你的路径，别提交它（已在 .gitignore）。
