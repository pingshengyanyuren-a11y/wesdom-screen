import requests
import time

url = "http://127.0.0.1:5001/api/batch_train_and_store"

print("正在启动全量预计算任务，请稍候...")
try:
    start_time = time.time()
    response = requests.post(url, timeout=300) # 设置较长超时
    if response.status_code == 200:
        data = response.json()
        duration = time.time() - start_time
        print(f"任务完成！耗时: {duration:.2f}秒")
        print(f"总测点数: {data.get('total_points')}")
        print(f"成功存库: {data.get('success_count')}")
    else:
        print(f"任务失败: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"请求发生错误: {e}")
