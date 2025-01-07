import time
from openai import OpenAI
import re
import json
import pandas as pd
import threading
from queue import Queue

def analyze_contents(contents, role, content_template):
    simplified_contents = []
    for _, row in contents.iterrows():
        simplified_contents.append({
            "title": row['title'],
            "content": row['content']
        })
    
    # 初始化 OpenAI 客户端
    client = OpenAI(
        api_key="sk-5e329eb2ca954936bc587878b2bef459",
        base_url="https://api.deepseek.com/v1"
    )
    
    try:
        time.sleep(1)
        completion = client.chat.completions.create(
            model='deepseek-chat',
            messages=[
                {"role": "system", "content": role},
                {
                    "role": "user",
                    "content": content_template.format(simplified_contents=simplified_contents)
                }
            ]
        )
        content = completion.choices[0].message.content
        return content
        
    except Exception as e:
        print(f"分析诗句时出错: {str(e)}")
        return None

def analyze_type(contents):
    role = "你是一个诗词分析专家。请按照固定格式返回诗词的体裁分析结果。"
    content_template = """必须按照以下JSON格式返回：
[
    {{"诗词题目": "题目1", "体裁": "体裁1"}},
    {{"诗词题目": "题目2", "体裁": "体裁2"}}
]
这是诗文内容{simplified_contents}"""
    return analyze_contents(contents, role, content_template)

def analyze_theme(contents):
    role = "你是一个诗词分析专家。请分析诗词的主题,只返回以下主题之一：自然、政治、边塞、爱情、哲理、咏史、咏物、友情、怀古、隐逸、社会现实、游仙"
    content_template = """必须按照以下JSON格式返回：
[
    {{"诗词题目": "题目1", "主题": "主题1"}},
    {{"诗词题目": "题目2", "主题": "主题2"}}
]
这是诗文内容{simplified_contents}"""
    return analyze_contents(contents, role, content_template)

def analyze_style(contents):
    simplified_contents = []
    for _, row in contents.iterrows():
        simplified_contents.append({
            "title": row['title'],
            "content": row['content']
        })
    
    # 初始化 OpenAI 客户端
    client = OpenAI(
        api_key="sk-5e329eb2ca954936bc587878b2bef459",
        base_url="https://api.deepseek.com/v1"
    )
    
    try:
        time.sleep(1)
        completion = client.chat.completions.create(
            model='deepseek-chat',
            messages=[
                {"role": "system", "content": "你是一个诗词分析专家。请按照固定格式返回诗词的体裁分析结果。"},
                {
                    "role": "user",
                    "content": f"""必须按照以下JSON格式返回：
[
    {{"诗词题目": "题目1", "体裁": "体裁1"}},
    {{"诗词题目": "题目2", "体裁": "体裁2"}}
]
这是诗文内容{simplified_contents}
"""
                }
            ]
        )
        content = completion.choices[0].message.content
        return content
        
    except Exception as e:
        print(f"分析诗句时出错: {str(e)}")
        return None

def update_df_with_analysis(content, batch_df, analysis_type):
    # 清理JSON字符串
    clean_json = re.sub(r'```json\n|\n```', '', content)
    
    try:
        # 解析JSON字符串为Python对象
        poems_info = json.loads(clean_json)
        # 创建type或theme列（如果不存在）
        column_name = 'type' if analysis_type == "type" else 'theme'
        if column_name not in batch_df.columns:
            batch_df[column_name] = '无' if analysis_type == "theme" else '古诗'
            
        # 更新每首诗的体裁或主题
        for poem in poems_info:
            title = poem['诗词题目']
            poem_value = poem['体裁' if analysis_type == "type" else '主题']
            # 只在当前批次中查找并更新
            mask = batch_df['title'] == title
            if mask.any():
                batch_df.loc[mask, column_name] = poem_value
            
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {str(e)}")
        print(f"问题JSON字符串: {clean_json}")
    except Exception as e:
        print(f"其他错误: {str(e)}")
    
    return batch_df

# 更新体裁更新函数
def update_df_with_types(content, batch_df):
    return update_df_with_analysis(content, batch_df, "type")

# 更新主题更新函数
def update_df_with_theme(content, batch_df):
    return update_df_with_analysis(content, batch_df, "theme")

def process_batch_thread(batch_df, result_queue):
    """
    线程处理函数，处理单个批次的数据
    """
    try:
        content = analyze_type(batch_df)
        if content:
            processed_batch = update_df_with_types(content, batch_df)
            result_queue.put((True, processed_batch))
        else:
            result_queue.put((False, batch_df))
    except Exception as e:
        print(f"线程处理错误: {str(e)}")
        result_queue.put((False, batch_df))

def batch_process_types(df, batch_size=5, thread_num=5):
    """
    使用多线程分批处理数据
    """
    processed_df = pd.DataFrame()
    result_queue = Queue()
    total_batches = len(df) // batch_size + (1 if len(df) % batch_size != 0 else 0)
    
    for i in range(0, total_batches, thread_num):
        threads = []
        # 创建并启动线程
        for j in range(thread_num):
            if i + j >= total_batches:
                break
                
            start_idx = (i + j) * batch_size
            end_idx = min((i + j + 1) * batch_size, len(df))
            print(f"处理批次 {i+j+1}/{total_batches} (记录 {start_idx+1}-{end_idx})")
            
            batch_df = df.iloc[start_idx:end_idx].copy()
            thread = threading.Thread(
                target=process_batch_thread,
                args=(batch_df, result_queue)
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 收集结果
        while not result_queue.empty():
            success, batch_result = result_queue.get()
            if success:
                processed_df = pd.concat([processed_df, batch_result])
            else:
                print(f"批次处理失败，跳过该批次")
    
    return processed_df

def process_batch_thread_theme(batch_df, result_queue):
    """
    线程处理函数，处理单个批次的数据
    """
    try:
        content = analyze_theme(batch_df)
        if content:
            processed_batch = update_df_with_theme(content, batch_df)
            result_queue.put((True, processed_batch))
        else:
            result_queue.put((False, batch_df))
    except Exception as e:
        print(f"线程处理错误: {str(e)}")
        result_queue.put((False, batch_df))

def batch_process_theme(df, batch_size=5, thread_num=5):
    """
    使用多线程分批处理数据
    """
    processed_df = pd.DataFrame()
    result_queue = Queue()
    total_batches = len(df) // batch_size + (1 if len(df) % batch_size != 0 else 0)
    
    for i in range(0, total_batches, thread_num):
        threads = []
        # 创建并启动线程
        for j in range(thread_num):
            if i + j >= total_batches:
                break
                
            start_idx = (i + j) * batch_size
            end_idx = min((i + j + 1) * batch_size, len(df))
            print(f"处理批次 {i+j+1}/{total_batches} (记录 {start_idx+1}-{end_idx})")
            
            batch_df = df.iloc[start_idx:end_idx].copy()
            thread = threading.Thread(
                target=process_batch_thread_theme,
                args=(batch_df, result_queue)
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 收集结果
        while not result_queue.empty():
            success, batch_result = result_queue.get()
            if success:
                processed_df = pd.concat([processed_df, batch_result])
            else:
                print(f"批次处理失败，跳过该批次")
    return processed_df

if __name__ == "__main__":
    df = pd.read_csv('data/legal.csv',encoding='utf-8')
    df = df.drop(df[df['title'] == '句'].index)
    df_processed = batch_process_types(df, batch_size=10, thread_num=5)
    df_processed.to_csv('data/legal.csv',index=False,encoding='utf-8')
    #481-490失败
