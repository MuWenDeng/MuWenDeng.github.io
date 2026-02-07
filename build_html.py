#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from pathlib import Path
from html import escape

def extract_toc(content):
    """提取目录结构（仅识别清晰的章节标题）"""
    lines = content.split('\n')
    toc = []
    toc_ids = set()  # 防止重复ID
    
    for line in lines:
        # 只提取格式规范的标题：数字开头，后面跟点和空格
        match = re.match(r'^(\d+(?:\.\d+){0,2})\.\s+(.+)$', line.strip())
        if match:
            number = match.group(1)
            title = match.group(2).strip()
            
            # 严格过滤：
            # 1. 标题长度至少4个字符（支持中文简短标题）
            # 2. 不包含特定关键词（排除步骤描述）
            # 3. 不以括号开头（排除"1)"这种格式）
            # 4. 不重复添加相同编号的标题
            skip_keywords = ['用户访问', '响应时间', 'JVM 已', 'Nginx', 'PHP 解释器', '启动 PHP', 
                           '收到请求', '直接调用', '可能创建', '重新解释', '累积使用']
            
            is_valid = (
                len(title) >= 4 and 
                not any(kw in title for kw in skip_keywords) and
                not title.startswith('http') and
                not line.strip().startswith(tuple([f'{i})' for i in range(10)])) and  # 排除"1)"格式
                number not in toc_ids
            )
            
            if is_valid:
                level = len(number.split('.'))
                toc_ids.add(number)
                toc.append({
                    'id': f"h-{number.replace('.', '-')}",
                    'number': number,
                    'title': title,
                    'level': level
                })
    
    return toc

def format_content_to_html(content, file_name):
    """将纯文本内容格式化为HTML"""
    lines = content.split('\n')
    html = []
    in_code_block = False
    code_lines = []
    brace_count = 0  # 追踪大括号
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测代码块标记
        if stripped.startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_lines = []
            else:
                # 代码块结束
                html.append('<pre><code>' + escape('\n'.join(code_lines)) + '</code></pre>')
                code_lines = []
                in_code_block = False
            i += 1
            continue
        
        if in_code_block:
            code_lines.append(line)
            i += 1
            continue
        
        # 检测标题
        title_match = re.match(r'^(\d+(?:\.\d+){0,2})\.\s+(.+)$', stripped)
        if title_match:
            number = title_match.group(1)
            title = title_match.group(2)
            level = len(number.split('.'))
            
            # 符合目录的才显示为标题，否则显示为普通段落
            skip_keywords = ['用户访问', '响应时间', 'JVM 已', 'Nginx', 'PHP 解释器', '启动 PHP', 
                           '收到请求', '直接调用', '可能创建', '重新解释', '累积使用']
            
            if len(title) >= 4 and not any(kw in title for kw in skip_keywords):
                h_tag = f"h{level + 1}"
                html.append(f'<{h_tag} id="h-{number.replace(".", "-")}" class="heading level-{level}">{escape(stripped)}</{h_tag}>')
            else:
                html.append(f'<p>{escape(line)}</p>')
            i += 1
            continue
        
        # 检测Java代码块（class、public、@注解等开头）
        java_keywords = ['class ', 'public ', 'private ', 'protected ', '@', 'import ', 'package ', 'interface ']
        is_java_line = any(stripped.startswith(kw) for kw in java_keywords)
        starts_with_brace = stripped and stripped[0] == '{'
        ends_with_brace = stripped and stripped[-1] == '{'
        
        # 如果是Java关键字开头，或者行尾有{，或者行首是{
        if is_java_line or starts_with_brace or ends_with_brace:
            # 开始收集代码块
            code_block = [line]
            brace_count = line.count('{') - line.count('}')
            i += 1
            
            # 如果当前行是声明但没有{，检查下一行是否是{
            if brace_count == 0 and i < len(lines) and lines[i].strip() and lines[i].strip()[0] == '{':
                code_block.append(lines[i])
                brace_count = lines[i].count('{') - lines[i].count('}')
                i += 1
            
            # 继续收集直到大括号平衡
            while i < len(lines) and brace_count > 0:
                code_block.append(lines[i])
                brace_count += lines[i].count('{') - lines[i].count('}')
                i += 1
            
            # 如果收集到了完整代码块
            if len(code_block) > 1 or brace_count == 0:
                html.append('<pre><code>' + escape('\n'.join(code_block)) + '</code></pre>')
                continue
            else:
                # 单行，作为普通段落
                html.append(f'<p>{escape(line)}</p>')
                continue
        
        # 检测缩进代码块（4空格或Tab缩进）
        if line.startswith('    ') or line.startswith('\t'):
            # 收集连续的缩进行
            code_block = [line]
            i += 1
            while i < len(lines) and (lines[i].startswith('    ') or lines[i].startswith('\t') or lines[i].strip() == ''):
                code_block.append(lines[i])
                i += 1
                if i < len(lines) and not lines[i].startswith('    ') and not lines[i].startswith('\t') and lines[i].strip():
                    break
            html.append('<pre><code>' + escape('\n'.join(code_block).rstrip()) + '</code></pre>')
            continue
        
        # 空行
        if not stripped:
            html.append('<div class="gap"></div>')
            i += 1
            continue
        
        # 普通段落
        html.append(f'<p>{escape(line)}</p>')
        i += 1
    
    return '\n'.join(html)

def generate_toc_html(toc_items):
    """生成树形目录HTML"""
    if not toc_items:
        return '<div class="empty-toc">暂无目录</div>'
    
    html = '<div class="toc-tree">'
    
    for item in toc_items:
        level = item['level']
        indent = (level - 1) * 15
        
        html += f'''
        <a href="#{item['id']}" class="toc-link level-{level}" style="padding-left: {indent}px;">
            <span class="toc-num">{item['number']}</span>
            <span class="toc-text">{escape(item['title'])}</span>
        </a>'''
    
    html += '</div>'
    return html

def main():
    base_dir = Path(__file__).parent
    file1 = base_dir / "学习Spring的记录.基础篇V1.txt"
    file2 = base_dir / "学习Spring的记录.面向招聘V2.txt"
    output = base_dir / "spring-learning-notes.html"
    
    print("📖 读取文件...")
    content1 = file1.read_text(encoding='utf-8')
    content2 = file2.read_text(encoding='utf-8')
    
    print("🔍 分析目录结构...")
    toc1 = extract_toc(content1)
    toc2 = extract_toc(content2)
    
    print(f"   📚 基础篇: {len(toc1)} 个章节")
    print(f"   💼 招聘篇: {len(toc2)} 个章节")
    
    print("✍️  格式化内容...")
    html1 = format_content_to_html(content1, file1.name)
    html2 = format_content_to_html(content2, file2.name)
    
    toc_html1 = generate_toc_html(toc1)
    toc_html2 = generate_toc_html(toc2)
    
    # 生成完整HTML文档
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spring 学习笔记 - Java 知识库</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            line-height: 1.7;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 20px auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2.5rem 2rem;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .header p {{
            font-size: 1rem;
            opacity: 0.9;
        }}
        
        /* Tabs */
        .tabs {{
            display: flex;
            background: #f5f7fa;
            border-bottom: 2px solid #e1e4e8;
        }}
        
        .tab {{
            flex: 1;
            padding: 1rem 2rem;
            border: none;
            background: transparent;
            font-size: 1.1rem;
            font-weight: 600;
            color: #666;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
        }}
        
        .tab:hover {{
            background: rgba(102, 126, 234, 0.05);
            color: #667eea;
        }}
        
        .tab.active {{
            color: #667eea;
            background: white;
        }}
        
        .tab.active::after {{
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            right: 0;
            height: 3px;
            background: #667eea;
        }}
        
        /* Content Area */
        .tab-panel {{
            display: none;
        }}
        
        .tab-panel.active {{
            display: flex;
        }}
        
        .layout {{
            display: flex;
            min-height: 70vh;
        }}
        
        /* Sidebar */
        .sidebar {{
            width: 280px;
            background: #f8f9fa;
            border-right: 1px solid #e1e4e8;
            overflow-y: auto;
            height: calc(100vh - 180px);
            flex-shrink: 0;
        }}
        
        .sidebar-title {{
            padding: 1.2rem 1rem;
            background: white;
            border-bottom: 2px solid #e1e4e8;
            font-weight: 700;
            color: #667eea;
            font-size: 0.95rem;
        }}
        
        .toc-tree {{
            padding: 1rem 0;
        }}
        
        .toc-link {{
            display: block;
            padding: 0.5rem 1rem;
            color: #555;
            text-decoration: none;
            font-size: 0.88rem;
            border-left: 3px solid transparent;
            transition: all 0.2s;
        }}
        
        .toc-link:hover {{
            background: rgba(102, 126, 234, 0.08);
            color: #667eea;
            border-left-color: #667eea;
        }}
        
        .toc-link.level-1 {{
            font-weight: 600;
            margin-top: 0.5rem;
        }}
        
        .toc-num {{
            color: #667eea;
            font-weight: 600;
            margin-right: 0.4rem;
        }}
        
        .toc-text {{
            word-break: break-word;
        }}
        
        /* Main Content */
        .main {{
            flex: 1;
            padding: 2.5rem 3rem;
            overflow-y: auto;
            height: calc(100vh - 180px);
        }}
        
        .heading {{
            margin: 2rem 0 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e8e8e8;
            color: #2c3e50;
            font-weight: 600;
        }}
        
        .heading.level-1 {{
            font-size: 1.8rem;
            color: #667eea;
            border-bottom-width: 3px;
        }}
        
        .heading.level-2 {{
            font-size: 1.4rem;
        }}
        
        .heading.level-3 {{
            font-size: 1.2rem;
            border-bottom: 1px solid #e8e8e8;
        }}
        
        .main p {{
            margin: 0.6rem 0;
            line-height: 1.8;
        }}
        
        .main .gap {{
            height: 0.8rem;
        }}
        
        .main pre {{
            background: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 1rem;
            overflow-x: auto;
            margin: 1rem 0;
            line-height: 1.5;
        }}
        
        .main code {{
            font-family: "SF Mono", Monaco, Consolas, "Courier New", monospace;
            font-size: 0.9em;
            color: #24292e;
        }}
        
        /* Footer */
        .footer {{
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 1.5rem;
            font-size: 0.9rem;
        }}
        
        /* Mobile Toggle */
        .mobile-toc-toggle {{
            display: none;
            background: #667eea;
            color: white;
            border: none;
            padding: 0.8rem 1rem;
            width: 100%;
            text-align: left;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        
        .mobile-toc-toggle:active {{
            background: #5568d3;
        }}
        
        .toc-tree.collapsed {{
            display: none;
        }}
        
        /* Responsive */
        @media (max-width: 1024px) {{
            .sidebar {{
                width: 240px;
            }}
            
            .main {{
                padding: 2rem;
            }}
        }}
        
        @media (max-width: 768px) {{
            .container {{
                margin: 0;
                border-radius: 0;
            }}
            
            .layout {{
                flex-direction: column;
            }}
            
            .sidebar {{
                width: 100%;
                height: auto;
                max-height: none;
                border-right: none;
                border-bottom: 2px solid #e1e4e8;
            }}
            
            .sidebar-title {{
                display: none;
            }}
            
            .mobile-toc-toggle {{
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .toc-tree {{
                max-height: 60vh;
                overflow-y: auto;
            }}
            
            .main {{
                padding: 1rem;
                height: auto;
                overflow-y: visible;
            }}
            
            .main pre {{
                font-size: 0.85rem;
                overflow-x: auto;
            }}
            
            .header h1 {{
                font-size: 1.8rem;
            }}
            
            .header p {{
                font-size: 0.9rem;
            }}
            
            .tab {{
                padding: 0.8rem 0.5rem;
                font-size: 0.9rem;
            }}
            
            .heading {{
                word-break: break-word;
            }}
        }}
        
        /* Scrollbar Style */
        .main::-webkit-scrollbar,
        .sidebar::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .main::-webkit-scrollbar-track,
        .sidebar::-webkit-scrollbar-track {{
            background: #f1f1f1;
        }}
        
        .main::-webkit-scrollbar-thumb,
        .sidebar::-webkit-scrollbar-thumb {{
            background: #888;
            border-radius: 4px;
        }}
        
        .main::-webkit-scrollbar-thumb:hover,
        .sidebar::-webkit-scrollbar-thumb:hover {{
            background: #667eea;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Spring 学习笔记</h1>
            <p>Java 核心知识 · Spring 框架精讲 · 面试必备</p>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab(0)">📚 基础篇</button>
            <button class="tab" onclick="switchTab(1)">💼 面向招聘</button>
        </div>
        
        <!-- 基础篇 -->
        <div class="tab-panel active">
            <div class="layout">
                <aside class="sidebar">
                    <div class="sidebar-title">📑 目录导航</div>
                    <button class="mobile-toc-toggle" onclick="toggleToc(this)">
                        <span>📑 目录导航</span>
                        <span class="toggle-icon">▼</span>
                    </button>
                    {toc_html1}
                </aside>
                <main class="main">
                    {html1}
                </main>
            </div>
        </div>
        
        <!-- 招聘篇 -->
        <div class="tab-panel">
            <div class="layout">
                <aside class="sidebar">
                    <div class="sidebar-title">📑 目录导航</div>
                    <button class="mobile-toc-toggle" onclick="toggleToc(this)">
                        <span>📑 目录导航</span>
                        <span class="toggle-icon">▼</span>
                    </button>
                    {toc_html2}
                </aside>
                <main class="main">
                    {html2}
                </main>
            </div>
        </div>
        
        <div class="footer">
            <p>📖 持续学习，不断进步 · 最后更新：2026年2月</p>
        </div>
    </div>
    
    <script>
        function switchTab(index) {{
            // 切换标签
            document.querySelectorAll('.tab').forEach((tab, i) => {{
                tab.classList.toggle('active', i === index);
            }});
            
            // 切换面板
            document.querySelectorAll('.tab-panel').forEach((panel, i) => {{
                panel.classList.toggle('active', i === index);
            }});
            
            // 移动端：收起所有目录
            if (window.innerWidth <= 768) {{
                document.querySelectorAll('.toc-tree').forEach(toc => {{
                    toc.classList.add('collapsed');
                }});
                document.querySelectorAll('.toggle-icon').forEach(icon => {{
                    icon.textContent = '▼';
                }});
            }}
        }}
        
        // 切换目录显示/隐藏（移动端）
        function toggleToc(button) {{
            const sidebar = button.closest('.sidebar');
            const tocTree = sidebar.querySelector('.toc-tree');
            const icon = button.querySelector('.toggle-icon');
            
            tocTree.classList.toggle('collapsed');
            icon.textContent = tocTree.classList.contains('collapsed') ? '▼' : '▲';
        }}
        
        // 平滑滚动
        document.querySelectorAll('.toc-link').forEach(link => {{
            link.addEventListener('click', function(e) {{
                e.preventDefault();
                
                // 获取目标元素ID
                const targetId = this.getAttribute('href').substring(1);
                
                // 找到当前激活的tab-panel
                const activePanel = document.querySelector('.tab-panel.active');
                
                if (activePanel) {{
                    // 在激活的面板中查找目标元素
                    const targetElement = activePanel.querySelector('#' + targetId);
                    const mainContent = activePanel.querySelector('.main');
                    
                    if (targetElement && mainContent) {{
                        // 移动端判断
                        const isMobile = window.innerWidth <= 768;
                        
                        if (isMobile) {{
                            // 移动端：收起目录并滚动页面
                            const tocTree = this.closest('.toc-tree');
                            if (tocTree) {{
                                tocTree.classList.add('collapsed');
                                const toggleBtn = activePanel.querySelector('.mobile-toc-toggle');
                                if (toggleBtn) {{
                                    const icon = toggleBtn.querySelector('.toggle-icon');
                                    if (icon) icon.textContent = '▼';
                                }}
                            }}
                            
                            // 滚动到目标元素（相对于整个容器）
                            setTimeout(() => {{
                                targetElement.scrollIntoView({{
                                    behavior: 'smooth',
                                    block: 'start'
                                }});
                            }}, 100);
                        }} else {{
                            // 桌面端：在主内容区内滚动
                            const targetPosition = targetElement.offsetTop - mainContent.offsetTop - 20;
                            mainContent.scrollTo({{
                                top: targetPosition,
                                behavior: 'smooth'
                            }});
                        }}
                    }}
                }}
            }});
        }});
        
        // 初始化：移动端默认收起目录
        if (window.innerWidth <= 768) {{
            document.querySelectorAll('.toc-tree').forEach(toc => {{
                toc.classList.add('collapsed');
            }});
        }}
    </script>
</body>
</html>"""
    
    print("💾 保存文件...")
    output.write_text(html_doc, encoding='utf-8')
    
    size_kb = output.stat().st_size / 1024
    print(f"\n✅ 生成成功!")
    print(f"📄 文件: {output.name}")
    print(f"💾 大小: {size_kb:.1f} KB")
    print(f"📊 统计:")
    print(f"   - 基础篇章节: {len(toc1)}")
    print(f"   - 招聘篇章节: {len(toc2)}")

if __name__ == "__main__":
    main()
