import requests

def get_us_proxy():
    try:
        # 示例代理 API：返回 {"ip": "xxx", "port": "xxx", "country": "US"}
        resp = requests.get("https://your-proxy-api.com/api/us")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("country", "") == "US":
                return data
    except Exception as e:
        print(f"[!] 获取美国代理失败: {e}")
    return None

