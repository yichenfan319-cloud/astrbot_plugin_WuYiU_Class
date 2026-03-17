import os
import re
import time
import json
import platform
import traceback
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Union, Dict

# ==================== AstrBot 导入（带容错） ====================
try:
    from astrbot.api.event import filter, AstrMessageEvent
    from astrbot.api.star import Context, Star
    from astrbot.api import logger
    ASTRBOT_AVAILABLE = True
except ImportError:
    ASTRBOT_AVAILABLE = False
    class MockLogger:
        def info(self, msg): print(f"[INFO] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
        def warning(self, msg): print(f"[WARN] {msg}")
    logger = MockLogger()
    
    class MockFilter:
        @staticmethod
        def command(cmd):
            def decorator(func): return func
            return decorator
    filter = MockFilter()
    
    class Context:
        pass
    class Star:
        def __init__(self, context): pass

from DrissionPage import ChromiumPage, ChromiumOptions
from bs4 import BeautifulSoup

# ==================== 数据类 ====================
@dataclass
class Course:
    name: str
    teacher: str
    location: str
    week_range: str
    day_of_week: str
    day_date: str
    time_slot: str
    sections: str
    credits: Optional[str] = None
    total_students: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)

# ==================== 课表获取器 ====================
class CourseFetcher:
    def __init__(self, username: str, password: str, headless=True, browser_path=None):
        self.username = username
        self.password = password
        
        co = ChromiumOptions()
        
        if browser_path:
            co.set_browser_path(browser_path)
            logger.info(f"[浏览器] 使用指定路径: {browser_path}")
        elif platform.system() == "Windows":
            auto_path = self._detect_windows_browser()
            if auto_path:
                co.set_browser_path(auto_path)
                logger.info(f"[浏览器] Windows自动检测: {auto_path}")
        
        co.headless(headless)
        co.set_argument('--incognito')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-gpu')
        co.set_argument('--window-size=1920,1080')
        co.set_argument('--ignore-certificate-errors')
        co.set_argument('--disable-web-security')
        
        if platform.system() == "Windows":
            co.set_argument('--disable-blink-features=AutomationControlled')
        
        self.page = ChromiumPage(co)
        logger.info("[浏览器] 初始化完成")
    
    def _detect_windows_browser(self):
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None
    
    def _get_current_week(self) -> int:
        try:
            result = self.page.run_js("""
                var select = document.getElementById('week');
                return select ? select.value : null;
            """)
            if result and str(result).isdigit():
                return int(result)
            html = self.page.html
            match = re.search(r'<option value="(\d+)"[^>]*selected', html)
            if match:
                return int(match.group(1))
            return 1
        except Exception as e:
            logger.warning(f"[周次获取] 失败: {e}")
            return 1
    
    def _select_week(self, week: Union[int, str]) -> bool:
        try:
            if week == "next":
                current = self._get_current_week()
                target = current + 1
                if target > 20:
                    logger.info(f"[周次] 当前已是第{current}周（最后一周）")
                    return False
                logger.info(f"[周次切换] {current} → {target}（下周）")
            else:
                target = int(week)
                if target < 1 or target > 20:
                    return False
                current = self._get_current_week()
                if current == target:
                    return True
                logger.info(f"[周次切换] {current} → {target}")
            
            js_code = f"""
            (function() {{
                var select = document.getElementById('week');
                if (!select) return 'not_found';
                select.value = '{target}';
                if (select.onchange) select.onchange();
                var evt = new Event('change', {{ bubbles: true }});
                select.dispatchEvent(evt);
                return 'success';
            }})()
            """
            result = self.page.run_js(js_code)
            logger.info(f"[周次切换] 结果: {result}")
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"[周次切换] 失败: {e}")
            return False
    
    def fetch_timetable(self, week: Union[int, str, None] = None) -> List[Course]:
        try:
            logger.info("[流程] 访问登录页...")
            self.page.get("https://sso.wuyiu.edu.cn/linkid/5")
            time.sleep(3)
            
            inputs = self.page.eles("tag:input")
            if len(inputs) >= 2:
                logger.info("[流程] 执行登录...")
                inputs[0].clear()
                inputs[0].input(self.username)
                inputs[1].clear()
                inputs[1].input(self.password)
                
                login_btn = self.page.ele("text=立即登录")
                if login_btn:
                    login_btn.click()
                    time.sleep(5)
                
                if "统一认证" in self.page.html and "立即登录" in self.page.html:
                    logger.error("[流程] 登录失败")
                    return []
                logger.info("[流程] 登录成功")
            
            logger.info("[流程] 进入教务首页...")
            self.page.get("https://jwxt.wuyiu.edu.cn/jsxsd/framework/xsMainV.htmlx")
            time.sleep(8)
            
            if "敏感操作记录" in self.page.html:
                self.page.get("https://jwxt.wuyiu.edu.cn/jsxsd/framework/xsMainV.htmlx")
                time.sleep(8)
            
            logger.info("[流程] 进入课表页面...")
            self.page.get("https://jwxt.wuyiu.edu.cn/jsxsd/framework/xsMainV_new.htmlx?t1=1")
            time.sleep(3)
            
            if week is not None:
                if not self._select_week(week):
                    if week == "next":
                        return []
            
            try:
                self.page.wait.ele_displayed('.qz-weeklyTable', timeout=15)
            except:
                pass
            
            temp_file = f"/tmp/kebiao_{week if week else 'current'}.html"
            if platform.system() == "Windows":
                temp_file = os.path.join(os.environ.get('TEMP', 'C:\\temp'), f"kebiao_{week if week else 'current'}.html")
            
            html = self.page.html
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            parser = CourseTableParser(temp_file)
            return parser.parse()
            
        except Exception as e:
            logger.error(f"[流程] 异常: {e}")
            traceback.print_exc()
            return []
    
    def close(self):
        try:
            self.page.quit()
            logger.info("[浏览器] 已关闭")
        except:
            pass

# ==================== 课表解析器 ====================
class CourseTableParser:
    def __init__(self, html_file: str):
        self.html_file = html_file
        self.soup = None
        self.courses: List[Course] = []
    
    def parse(self) -> List[Course]:
        with open(self.html_file, 'r', encoding='utf-8') as f:
            self.soup = BeautifulSoup(f, 'html.parser')
        
        table = self.soup.find('table', class_='qz-weeklyTable')
        if not table:
            raise ValueError("未找到课表表格")
        
        headers = self._parse_headers(table)
        tbody = table.find('tbody', class_='qz-weeklyTable-thbody') or table.find('tbody')
        rows = tbody.find_all('tr', class_='qz-weeklyTable-tr')
        
        for row in rows:
            self._parse_row(row, headers)
        
        return self.courses
    
    def _parse_headers(self, table):
        thead = table.find('thead', class_='qz-weeklyTable-thead') or table.find('thead')
        ths = thead.find('tr').find_all('th', class_='qz-weeklyTable-th')
        headers = []
        for i, th in enumerate(ths[1:], start=0):
            spans = th.find_all('span')
            if len(spans) >= 2:
                headers.append({
                    'index': i,
                    'day': spans[0].text.strip(),
                    'date': spans[1].text.strip()
                })
        return headers
    
    def _parse_row(self, row, headers):
        tds = row.find_all('td', class_='qz-weeklyTable-td')
        if not tds:
            return
        
        time_slot = self._extract_time_slot(tds[0])
        if not time_slot:
            return
        
        for day_index, td in enumerate(tds[1:]):
            if day_index >= len(headers):
                break
            header = headers[day_index]
            course_lists = td.find('ul', class_='courselists')
            if course_lists:
                items = course_lists.find_all('li', class_='courselists-item')
                for item in items:
                    course = self._extract_course(item, time_slot, header['day'], header['date'])
                    if course:
                        self.courses.append(course)
    
    def _extract_time_slot(self, cell):
        try:
            title = cell.find('div', class_='index-title')
            return title.text.strip() if title else None
        except:
            return None
    
    def _extract_course(self, item, time_slot, day_of_week, day_date):
        try:
            name_div = item.find('div', class_='qz-hasCourse-title')
            name = name_div.text.strip() if name_div else "未知课程"
            
            tooltip = item.find_next_sibling('div', class_='qz-tooltip')
            teacher, location, week_range, sections, credits, total = "", "", "", "", "", ""
            
            if tooltip:
                tooltip_details = tooltip.find_all('div', class_='qz-tooltipContent-detailitem')
                for div in tooltip_details:
                    text = div.text.strip()
                    if text.startswith('教师：'):
                        teacher = text.replace('教师：', '')
                    elif text.startswith('上课地点：'):
                        location = text.replace('上课地点：', '')
                    elif text.startswith('周次：'):
                        week_range = text.replace('周次：', '')
                    elif text.startswith('节次：'):
                        sections = text.replace('节次：', '')
                    elif text.startswith('学分：'):
                        credits = text.replace('学分：', '')
                    elif text.startswith('总人数：'):
                        total = text.replace('总人数：', '')
            
            if not location or not teacher:
                details = item.find_all('div', class_='qz-hasCourse-detailitem')
                detail_texts = []
                for div in details:
                    text = div.text.strip()
                    if text and not text.startswith('fzm-check-control'):
                        detail_texts.append(text)
                
                for text in detail_texts:
                    if text.startswith('教师：'):
                        if not teacher:
                            teacher = text.replace('教师：', '')
                    elif text.startswith('节次：'):
                        if not sections:
                            sections = text.replace('节次：', '')
                    elif text.startswith('周次：'):
                        if not week_range:
                            week_range = text.replace('周次：', '')
                    elif text.startswith('总人数：'):
                        if not total:
                            total = text.replace('总人数：', '')
                    elif text.startswith('学分：'):
                        if not credits:
                            credits = text.replace('学分：', '')
                    elif not text.endswith('小节') and not text.startswith('['):
                        if not location:
                            location = text
            
            if not location:
                location = "未知地点"
            
            if not sections:
                sections = self._convert_time_slot(time_slot)
            
            return Course(
                name=name, 
                teacher=teacher or "未知教师", 
                location=location,
                week_range=week_range,
                day_of_week=day_of_week,
                day_date=day_date,
                time_slot=time_slot,
                sections=sections,
                credits=credits,
                total_students=total
            )
        except Exception as e:
            logger.error(f"[解析] 课程解析失败: {e}")
            return None
    
    def _convert_time_slot(self, time_slot: str) -> str:
        mapping = {
            '第一二节': '01~02小节',
            '第三四节': '03~04小节',
            '第五六节': '05~06小节',
            '第七八节': '07~08小节',
            '第九十节': '09~10小节',
        }
        return mapping.get(time_slot, time_slot)
    
    def get_today_courses(self, courses: List[Course] = None) -> List[Course]:
        if courses is None:
            courses = self.courses
        weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        today = weekdays[datetime.now().weekday()]
        return [c for c in courses if c.day_of_week == today]
    
    def get_specific_day_courses(self, courses: List[Course], target_day: str) -> List[Course]:
        return [c for c in courses if c.day_of_week == target_day]

# ==================== 格式化辅助函数 ====================
def get_time_period(sections: str) -> str:
    match = re.search(r'(\d+)~(\d+)', sections)
    if match:
        start = int(match.group(1))
        if 1 <= start <= 4:
            return "上午"
        elif 5 <= start <= 8:
            return "下午"
        elif start >= 9:
            return "晚上"
    
    if '第一二节' in sections or '第三四节' in sections:
        return "上午"
    elif '第五六节' in sections or '第七八节' in sections:
        return "下午"
    elif '第九十节' in sections:
        return "晚上"
    
    return "未知时段"

def get_friendly_sections(sections: str) -> str:
    match = re.search(r'(\d+)~(\d+)', sections)
    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        return f"第{start}-{end}节"
    
    if '第一二节' in sections:
        return "第1-2节"
    elif '第三四节' in sections:
        return "第3-4节"
    elif '第五六节' in sections:
        return "第5-6节"
    elif '第七八节' in sections:
        return "第7-8节"
    elif '第九十节' in sections:
        return "第9-10节"
    
    return sections

def format_single_course(c: Course) -> str:
    friendly_section = get_friendly_sections(c.sections)
    lines = []
    lines.append(f"⏰{friendly_section}  |  {c.name}")
    lines.append(f"📍上课地点  |  {c.location}")
    lines.append(f"👨‍🏫上课教师  |  {c.teacher}")
    return "\n".join(lines)

def format_courses_list(title: str, courses: List[Course]) -> str:
    if not courses:
        return f"🎉 {title}没有课！可以休息啦~"
    
    morning = [c for c in courses if get_time_period(c.sections) == "上午"]
    afternoon = [c for c in courses if get_time_period(c.sections) == "下午"]
    evening = [c for c in courses if get_time_period(c.sections) == "晚上"]
    
    lines = [f"📅 {title} 共 {len(courses)} 节课："]
    
    if morning:
        lines.append("\n【上午】")
        for c in morning:
            lines.append(format_single_course(c))
            lines.append("")
    
    if afternoon:
        lines.append("【下午】")
        for c in afternoon:
            lines.append(format_single_course(c))
            lines.append("")
    
    if evening:
        lines.append("【晚上】")
        for c in evening:
            lines.append(format_single_course(c))
            lines.append("")
    
    return "\n".join(lines)

def format_week_by_day(title: str, courses: List[Course]) -> str:
    if not courses:
        return f"🎉 {title}没有课！可以休息啦~"
    
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    lines = [f"📅 {title} 共 {len(courses)} 门课程：\n"]
    
    for day in weekdays:
        day_courses = [c for c in courses if c.day_of_week == day]
        if not day_courses:
            continue
        
        lines.append(f"{day}")
        lines.append("=" * 20)
        
        morning = [c for c in day_courses if get_time_period(c.sections) == "上午"]
        afternoon = [c for c in day_courses if get_time_period(c.sections) == "下午"]
        evening = [c for c in day_courses if get_time_period(c.sections) == "晚上"]
        
        if morning:
            lines.append("\n【上午】")
            for c in morning:
                lines.append(format_single_course(c))
                lines.append("")
        
        if afternoon:
            lines.append("【下午】")
            for c in afternoon:
                lines.append(format_single_course(c))
                lines.append("")
        
        if evening:
            lines.append("【晚上】")
            for c in evening:
                lines.append(format_single_course(c))
                lines.append("")
        
        lines.append("")
    
    return "\n".join(lines)

# ==================== AstrBot 插件主类（官方标准写法） ====================
class WuyiKebiaoPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        
        # 官方标准写法：保存整个 config 对象（AstrBotConfig 继承自 Dict）
        self.config = config or {}
        self.data_dir = ""
        self.json_file = ""
        self.courses: List[Course] = []
        
        # 初始化数据目录
        if hasattr(context, 'data_path'):
            self.data_dir = context.data_path
        else:
            self.data_dir = os.path.join(os.path.dirname(__file__), "data")
        
        os.makedirs(self.data_dir, exist_ok=True)
        self.json_file = os.path.join(self.data_dir, "courses.json")
        self._load_cache()
        
        # 调试信息
        if self.config:
            logger.info(f"[武夷课表] 配置已加载: {list(self.config.keys())}")
            # 检查是否有账号（脱敏显示）
            if self.config.get("username"):
                logger.info(f"[武夷课表] 账号状态: 已配置 ({str(self.config.get('username'))[:4]}****)")
            else:
                logger.info("[武夷课表] 账号状态: 未配置")
        else:
            logger.warning("[武夷课表] 配置为空，请在 WebUI 插件配置中设置")
    
    def _get_credentials(self):
        """获取账号密码（支持环境变量覆盖配置）"""
        username = os.environ.get("WUYI_USERNAME") or self.config.get("username", "")
        password = os.environ.get("WUYI_PASSWORD") or self.config.get("password", "")
        browser_path = os.environ.get("BROWSER_PATH") or self.config.get("browser_path", "/usr/bin/chromium")
        return username.strip(), password.strip(), browser_path.strip() if browser_path else "/usr/bin/chromium"
    
    def _load_cache(self):
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.courses = [Course(**item) for item in data]
                logger.info(f"[缓存] 已加载 {len(self.courses)} 门课程")
            except Exception as e:
                logger.error(f"[缓存] 加载失败: {e}")
                self.courses = []
    
    def _save_cache(self, courses: List[Course]):
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump([c.to_dict() for c in courses], f, ensure_ascii=False, indent=2)
            logger.info(f"[缓存] 已保存 {len(courses)} 门课程")
        except Exception as e:
            logger.error(f"[缓存] 保存失败: {e}")
    
    def _get_relative_day_info(self, offset: int) -> tuple:
        weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        today_idx = datetime.now().weekday()
        target_idx = (today_idx + offset) % 7
        target_day = weekdays[target_idx]
        
        is_next_week = target_idx < today_idx
        desc = f"明天（{target_day}）" if offset == 1 else f"后天（{target_day}）"
        if is_next_week:
            desc += "（下周）"
        
        return target_day, is_next_week, desc

    @filter.command("更新课表")
    async def update_kebiao(self, event: AstrMessageEvent):
        username, password, browser_path = self._get_credentials()
        
        if not username or not password:
            yield event.plain_result("❌ 未配置学号或密码，请在 AstrBot WebUI → 插件配置 → 武夷课表 中设置")
            return
        
        yield event.plain_result("⏳ 正在登录教务系统获取当前周课表...")
        
        fetcher = None
        try:
            fetcher = CourseFetcher(
                username, 
                password, 
                headless=True,
                browser_path=browser_path
            )
            courses = fetcher.fetch_timetable(week=None)
            
            if not courses:
                yield event.plain_result("❌ 获取课表失败，请检查账号密码或网络")
                return
            
            self.courses = courses
            self._save_cache(courses)
            
            result = format_week_by_day("当前周", courses)
            yield event.plain_result(f"✅ 更新成功！\n{result}\n\n💡 提示：发送\"明天课表\"查看明日安排")
            
        except Exception as e:
            logger.error(f"[命令] 更新课表异常: {e}")
            yield event.plain_result(f"❌ 出错: {str(e)}")
        finally:
            if fetcher:
                fetcher.close()

    @filter.command("下周课表")
    async def next_week_courses(self, event: AstrMessageEvent):
        username, password, browser_path = self._get_credentials()
        
        if not username or not password:
            yield event.plain_result("❌ 未配置学号或密码，请在插件配置中设置")
            return
            
        yield event.plain_result("⏳ 正在查询下周课表...")
        
        fetcher = None
        try:
            fetcher = CourseFetcher(
                username,
                password,
                headless=True,
                browser_path=browser_path
            )
            courses = fetcher.fetch_timetable(week="next")
            
            if not courses:
                yield event.plain_result("❌ 获取失败或当前已是最后一周（第20周）")
                return
            
            result = format_week_by_day("下周", courses)
            yield event.plain_result(result)
            
        except Exception as e:
            logger.error(f"[命令] 下周课表异常: {e}")
            yield event.plain_result(f"❌ 出错: {str(e)}")
        finally:
            if fetcher:
                fetcher.close()

    @filter.command("第 {week} 周课表")
    async def specific_week(self, event: AstrMessageEvent, week: str):
        username, password, browser_path = self._get_credentials()
        
        if not username or not password:
            yield event.plain_result("❌ 未配置学号或密码，请在插件配置中设置")
            return
            
        try:
            week_num = int(week)
            if week_num < 1 or week_num > 20:
                yield event.plain_result("❌ 周次必须在 1-20 之间")
                return
        except ValueError:
            yield event.plain_result("❌ 周次必须是数字，如：第 3 周课表")
            return
        
        yield event.plain_result(f"⏳ 正在查询第 {week_num} 周课表...")
        
        fetcher = None
        try:
            fetcher = CourseFetcher(
                username,
                password,
                headless=True,
                browser_path=browser_path
            )
            courses = fetcher.fetch_timetable(week=week_num)
            
            if not courses:
                yield event.plain_result("❌ 获取失败")
                return
            
            result = format_week_by_day(f"第{week_num}周", courses)
            yield event.plain_result(result)
            
        except Exception as e:
            logger.error(f"[命令] 指定周课表异常: {e}")
            yield event.plain_result(f"❌ 出错: {str(e)}")
        finally:
            if fetcher:
                fetcher.close()

    @filter.command("今天有什么课")
    async def today_courses(self, event: AstrMessageEvent):
        if not self.courses:
            yield event.plain_result("📭 还没有课表数据，请先发送 \"更新课表\"")
            return
        
        parser = CourseTableParser("")
        today_list = parser.get_today_courses(self.courses)
        
        if not today_list:
            weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            today = weekdays[datetime.now().weekday()]
            yield event.plain_result(f"🎉 今天（{today}）没有课！可以休息啦~")
            return
        
        result = format_courses_list("今天", today_list)
        yield event.plain_result(result)

    @filter.command("明天课表")
    async def tomorrow_courses(self, event: AstrMessageEvent):
        username, password, browser_path = self._get_credentials()
        
        if not username or not password:
            yield event.plain_result("❌ 未配置学号或密码，请在插件配置中设置")
            return
            
        target_day, is_next_week, desc = self._get_relative_day_info(1)
        
        if is_next_week:
            yield event.plain_result(f"⏳ 正在查询明天（{target_day}，下周）的课表...")
            
            fetcher = None
            try:
                fetcher = CourseFetcher(
                    username,
                    password,
                    headless=True,
                    browser_path=browser_path
                )
                courses = fetcher.fetch_timetable(week="next")
                
                if not courses:
                    yield event.plain_result("❌ 获取下周课表失败")
                    return
                
                parser = CourseTableParser("")
                tomorrow_list = parser.get_specific_day_courses(courses, target_day)
                result = format_courses_list(f"明天（{target_day}）", tomorrow_list)
                yield event.plain_result(result)
                
            except Exception as e:
                logger.error(f"[命令] 明天课表异常: {e}")
                yield event.plain_result(f"❌ 出错: {str(e)}")
            finally:
                if fetcher:
                    fetcher.close()
        else:
            if not self.courses:
                yield event.plain_result("📭 还没有课表数据，请先发送 \"更新课表\"")
                return
            
            parser = CourseTableParser("")
            tomorrow_list = parser.get_specific_day_courses(self.courses, target_day)
            result = format_courses_list(f"明天（{target_day}）", tomorrow_list)
            yield event.plain_result(result)

    @filter.command("后天课表")
    async def day_after_tomorrow_courses(self, event: AstrMessageEvent):
        username, password, browser_path = self._get_credentials()
        
        if not username or not password:
            yield event.plain_result("❌ 未配置学号或密码，请在插件配置中设置")
            return
            
        target_day, is_next_week, desc = self._get_relative_day_info(2)
        
        if is_next_week:
            yield event.plain_result(f"⏳ 正在查询后天（{target_day}，下周）的课表...")
            
            fetcher = None
            try:
                fetcher = CourseFetcher(
                    username,
                    password,
                    headless=True,
                    browser_path=browser_path
                )
                courses = fetcher.fetch_timetable(week="next")
                
                if not courses:
                    yield event.plain_result("❌ 获取下周课表失败")
                    return
                
                parser = CourseTableParser("")
                day_after_list = parser.get_specific_day_courses(courses, target_day)
                result = format_courses_list(f"后天（{target_day}）", day_after_list)
                yield event.plain_result(result)
                
            except Exception as e:
                logger.error(f"[命令] 后天课表异常: {e}")
                yield event.plain_result(f"❌ 出错: {str(e)}")
            finally:
                if fetcher:
                    fetcher.close()
        else:
            if not self.courses:
                yield event.plain_result("📭 还没有课表数据，请先发送 \"更新课表\"")
                return
            
            parser = CourseTableParser("")
            day_after_list = parser.get_specific_day_courses(self.courses, target_day)
            result = format_courses_list(f"后天（{target_day}）", day_after_list)
            yield event.plain_result(result)

    @filter.command("本周课表")
    async def current_week_overview(self, event: AstrMessageEvent):
        if not self.courses:
            yield event.plain_result("📭 还没有课表数据，请先发送 \"更新课表\"")
            return
        
        result = format_week_by_day("本周", self.courses)
        yield event.plain_result(result)


# ==================== Windows 本地测试入口 ====================
if __name__ == "__main__":
    print("="*60)
    print("武夷学院课表插件 - Windows本地测试模式")
    print("="*60)
    
    try:
        from DrissionPage import __version__ as dp_version
        print(f"✅ DrissionPage 已安装 (v{dp_version})")
    except ImportError:
        print("❌ 缺少 DrissionPage: pip install DrissionPage")
        exit(1)
    
    try:
        from bs4 import BeautifulSoup
        print("✅ BeautifulSoup4 已安装")
    except ImportError:
        print("❌ 缺少 BeautifulSoup4: pip install beautifulsoup4")
        exit(1)
    
    TEST_USERNAME = os.environ.get("WUYI_USERNAME", "")
    TEST_PASSWORD = os.environ.get("WUYI_PASSWORD", "")
    TEST_HEADLESS = False
    
    if not TEST_USERNAME or not TEST_PASSWORD:
        print("\n⚠️  请设置环境变量 WUYI_USERNAME 和 WUYI_PASSWORD")
        print("示例：set WUYI_USERNAME=20251481201")
        print("      set WUYI_PASSWORD=你的密码")
        input("\n按回车键退出...")
        exit(1)
    
    print(f"\n[配置] 账号: {TEST_USERNAME}")
    print(f"[配置] 密码: {'*' * len(TEST_PASSWORD)}")
    print(f"[配置] 模式: {'无痕' if TEST_HEADLESS else '可视化（调试）'}")
    print("-"*60)
    
    class LocalTester(WuyiKebiaoPlugin):
        def __init__(self):
            # 模拟 Context
            class MockContext:
                data_path = os.path.join(os.path.expanduser("~"), "Documents", "WuyiKebiao")
            
            # 构造 config 字典
            config = {
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
                "browser_path": ""
            }
            
            super().__init__(MockContext(), config)
    
    plugin = LocalTester()
    
    async def interactive_menu():
        while True:
            print("\n功能菜单:")
            print("1. 更新课表（当前周）")
            print("2. 查看今天有什么课")
            print("3. 查看明天课表（智能判断下周）")
            print("4. 查看后天课表（智能判断下周）")
            print("5. 查看下周课表")
            print("6. 查看指定周课表(1-20)")
            print("7. 查看本周课表概览")
            print("0. 退出")
            
            choice = input("\n请选择: ").strip()
            
            class MockEvent:
                async def plain_result(self, text):
                    print(f"\n{'='*50}\n{text}\n{'='*50}\n")
            
            async def run_cmd(cmd_func, *args):
                async for msg in cmd_func(MockEvent(), *args):
                    pass
            
            import asyncio
            
            if choice == "1":
                await run_cmd(plugin.update_kebiao)
            elif choice == "2":
                await run_cmd(plugin.today_courses)
            elif choice == "3":
                await run_cmd(plugin.tomorrow_courses)
            elif choice == "4":
                await run_cmd(plugin.day_after_tomorrow_courses)
            elif choice == "5":
                await run_cmd(plugin.next_week_courses)
            elif choice == "6":
                week = input("请输入周次(1-20): ").strip()
                try:
                    await run_cmd(plugin.specific_week, week)
                except ValueError:
                    print("❌ 请输入数字")
            elif choice == "7":
                await run_cmd(plugin.current_week_overview)
            elif choice == "0":
                print("退出")
                break
            else:
                print("无效选项")
    
    import asyncio
    asyncio.run(interactive_menu())