# sub2api OpenAI-compatible /v1/images/* 接口文档

本文档只描述本项目后端异步任务实际调用 OpenAI-compatible `/v1/images/*` 系列接口。  
本项目当前只调用两个上游接口：

- `POST /v1/images/generations`
- `POST /v1/images/edits`

## 基础地址

上游基础地址来自配置：

```text
SUB2API_BASE_URL=https://geekai.live/v1
```

后端代码会将以下相对路径拼接到 `SUB2API_BASE_URL` 后：

```text
{SUB2API_BASE_URL}/images/generations
{SUB2API_BASE_URL}/images/edits
```

## 认证

所有上游请求都会携带：

```http
Authorization: Bearer <api_key>
```

`api_key` 来自当前用户的配置。登录用户使用托管 Key 时，会按用户在前端选择的 sub2api 分组获取对应 Key。

## 异步调用机制

本项目不会在用户请求中同步等待 sub2api 完成，而是：

```text
1. 创建 image_tasks 任务记录
2. 后台 asyncio task 执行上游 /v1/images/* 调用
3. 上游返回 b64_json
4. 后端解码并保存到 STORAGE_DIR/images
5. 写入 image_history
6. 前端轮询任务状态
```

后台任务异常处理：

- 任务开始后状态置为 `running`
- 成功后状态置为 `succeeded`
- 失败后状态置为 `failed`
- 429、502、503、504 会最多重试 3 次

## 文生图：POST /v1/images/generations

### 请求

```http
POST {SUB2API_BASE_URL}/images/generations
Content-Type: application/json
Authorization: Bearer <api_key>
```

### 请求体

本项目实际发送 JSON：

```json
{
  "model": "gpt-image-2",
  "prompt": "a futuristic city at night",
  "size": "2560x1440",
  "quality": "auto",
  "n": 1,
  "response_format": "b64_json"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `model` | string | 是 | 图片模型，默认来自后端配置 |
| `prompt` | string | 是 | 提示词 |
| `size` | string | 是 | 后端换算后的尺寸，例如 `1440x1440`、`2560x1440` |
| `quality` | string | 是 | 图片质量，例如 `auto`、`medium`、`high` |
| `response_format` | string | 是 | 本项目固定传 `b64_json` |
| `background` | string | 否 | 前端有传值时透传 |
| `output_format` | string | 否 | 前端有传值时透传 |

### curl 示例

```bash
curl -X POST "https://geekai.live/v1/images/generations" \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "a futuristic city at night",
    "size": "2560x1440",
    "quality": "auto",
    "response_format": "b64_json"
  }'
```

### 期望响应

本项目期望上游返回 OpenAI-compatible 格式：

```json
{
  "created": 1710000000,
  "data": [
    {
      "b64_json": "iVBORw0KGgo...",
      "revised_prompt": "optional revised prompt"
    }
  ],
  "usage": {
    "total_tokens": 1
  }
}
```

本项目会读取：

- `data[].b64_json`：解码并保存为图片文件
- `data[].revised_prompt`：保存到历史记录
- `created`、`usage`：保存到任务结果和账单元数据

## 改图：POST /v1/images/edits

### 请求

```http
POST {SUB2API_BASE_URL}/images/edits
Content-Type: multipart/form-data
Authorization: Bearer <api_key>
```

### 表单字段

本项目实际发送 `multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `model` | string | 是 | 图片模型 |
| `prompt` | string | 是 | 改图提示词 |
| `size` | string | 是 | 后端换算后的尺寸 |
| `quality` | string | 是 | 图片质量 |
| `response_format` | string | 是 | 固定为 `b64_json` |
| `image` | file[] | 是 | 参考图文件，可多张；字段名重复为 `image` |
| `mask` | file | 否 | 蒙版图 |

注意：本项目对 `/v1/images/edits` 的输入参考图使用 multipart 文件上传，不是 base64。

### curl 示例

```bash
curl -X POST "https://geekai.live/v1/images/edits" \
  -H "Authorization: Bearer sk-xxx" \
  -F "model=gpt-image-2" \
  -F "prompt=turn this product photo into a cyberpunk poster" \
  -F "size=1440x1440" \
  -F "quality=auto" \
  -F "response_format=b64_json" \
  -F "image=@./source.png;type=image/png"
```

多张参考图：

```bash
curl -X POST "https://geekai.live/v1/images/edits" \
  -H "Authorization: Bearer sk-xxx" \
  -F "model=gpt-image-2" \
  -F "prompt=combine the style of both references" \
  -F "size=1440x1440" \
  -F "quality=auto" \
  -F "response_format=b64_json" \
  -F "image=@./source.png;type=image/png" \
  -F "image=@./style.png;type=image/png"
```

带 mask：

```bash
curl -X POST "https://geekai.live/v1/images/edits" \
  -H "Authorization: Bearer sk-xxx" \
  -F "model=gpt-image-2" \
  -F "prompt=replace the background with a neon city" \
  -F "size=1440x1440" \
  -F "quality=auto" \
  -F "response_format=b64_json" \
  -F "image=@./source.png;type=image/png" \
  -F "mask=@./mask.png;type=image/png"
```

### 期望响应

同文生图接口，本项目期望：

```json
{
  "created": 1710000000,
  "data": [
    {
      "b64_json": "iVBORw0KGgo...",
      "revised_prompt": "optional revised prompt"
    }
  ],
  "usage": {
    "total_tokens": 2
  }
}
```

## 尺寸换算规则

本项目内部允许传 `1K`、`2K`、`4K` 档位和比例，调用 sub2api 前会换算成具体尺寸。

| 档位 | 1:1 | 16:9 | 9:16 | 3:2 | 2:3 | 4:3 | 3:4 |
|---|---|---|---|---|---|---|---|
| `1K` | `1088x1088` | `2048x1152` | `1152x2048` | `1632x1088` | `1088x1632` | `1472x1104` | `1104x1472` |
| `2K` | `1440x1440` | `2560x1440` | `1440x2560` | `2160x1440` | `1440x2160` | `1920x1440` | `1440x1920` |
| `4K` | 不支持 | `3840x2160` | `2160x3840` | `3840x2560` | `2560x3840` | `3840x2880` | `2880x3840` |

如果直接传具体尺寸，则要求：

- 宽高乘积不能低于 `1024 * 1024`
- 宽高必须都能被 16 整除
- 任意边不能超过 3840
- 正方形尺寸大于 `2048x2048` 不支持

## 错误处理

上游返回 HTTP `>= 400` 时，本项目会解析错误信息并将任务标记为 `failed`。

重试状态码：

```text
429, 502, 503, 504
```

最大重试次数：

```text
3
```

## 返回图片处理

本项目固定要求上游返回：

```json
{
  "b64_json": "..."
}
```

处理方式：

```text
b64_json -> base64 decode -> 写入 STORAGE_DIR/images/{history_id}.png -> 返回 /storage/images/{history_id}.png
```

如果上游返回 `url` 而不是 `b64_json`，当前保存逻辑也支持下载该 URL 并落盘，但本项目实际请求默认要求 `b64_json`。

## 相关代码

| 逻辑 | 文件 |
|---|---|
| 异步任务执行、请求 payload 组装 | `backend/app/main.py` |
| 调用 `/images/generations`、`/images/edits` | `backend/app/provider.py` |
| 上游返回图片保存 | `backend/app/storage.py` |
