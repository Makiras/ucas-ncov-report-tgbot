import re
from typing import Dict, Optional
import logging
import requests
import datetime
from pytz import timezone as pytz_timezone
import logging
import json
from .config import *

_logger = logging.getLogger(__name__)

class UsernameNotSet(Exception):
    pass

def match_re_group1(re_str: str, text: str) -> str:
    """
    在 text 中匹配正则表达式 re_str，返回第 1 个捕获组（即首个用括号包住的捕获组）
    :param re_str: 正则表达式（字符串）
    :param text: 要被匹配的文本
    :return: 第 1 个捕获组
    """
    match = re.search(re_str, text)
    if match is None:
        raise ValueError(f'在文本中匹配 {re_str} 失败，没找到任何东西。\n请阅读脚本文档中的“使用前提”部分。')

    return match.group(1)

def extract_post_data(json_txt: str) -> Dict[str, str]:
    """
    从上报页面的 数据接口 中，提取出上报 API 所需要填写的参数。
    :return: 最终 POST 的参数（使用 dict 表示）
    """

    # 检查数据是否足够长
    _logger.debug(f"\n{len(json_txt)} bytes of json data received.")
    if len(json_txt) < REASONABLE_LENGTH:
        _logger.debug(f'\nshort old_data: {json_txt}\n')
        raise ValueError('获取到的数据过短。请阅读脚本文档的“使用前提”部分')

    old_data = json.loads(json_txt)['d']
    _logger.debug(f'\nold_data: {old_data}\n')

    new_data = {
        'realname': old_data['realname'],
        'number': old_data['number'],
        'szgj_api_info': old_data['szgj_api_info'], # 似乎没用？
        # 'szgj': old_data['szgj'],# 2021.8.1 del 
        # 'old_sfzx': old_data['sfzx'],# 2021.8.1 del
        'sfzx': old_data['sfzx'], #是否在校
        # 'szdd': old_data['szdd'], #所在地点
        'szdd': '国内', #所在地点 update 2022.2.9
        # 'sflgj': old_data['sflgj'],
        'ismoved': 0,  # 如果前一天位置变化这个值会为1，第二天仍然获取到昨天的1，而事实上位置是没变化的，所以置0
        # 'ismoved': old_data['ismoved'],
        'tw': old_data['tw'], #体温
        # 'bztcyy': old_data['bztcyy'], # 2021.8.1 del
        # 'sftjwh': old_data['sfsfbh'],  # 2020.9.16 del
        # 'sftjhb': old_data['sftjhb'],  # 2020.9.16 del
        'sfcxtz': old_data['sfcxtz'], #todo 是否出现症状
        # 'sfyyjc': old_data['sfyyjc'],# 2021.8.1 del
        # 'jcjgqr': old_data['jcjgqr'],# 2021.8.1 del
        # 'sfjcwhry': old_data['sfjcwhry'],  # 2020.9.16 del
        # 'sfjchbry': old_data['sfjchbry'],  # 2020.9.16 del
        'sfjcbh': old_data['sfjcbh'],  # 是否接触病患
        # 'jcbhlx': old_data['jcbhlx'], # 2021.1.29 del 接触病患类型
        'sfcyglq': old_data['sfcyglq'],  # 是否处于隔离期（观察期
        # 'gllx': old_data['gllx'],   # 2021.1.29 del 隔离类型
        'sfcxzysx': old_data['sfcxzysx'], #
        # 'old_szdd': old_data['szdd'],# 2021.8.1 del
        'geo_api_info': old_data['old_city'],  # 保持昨天的结果
        'old_city': old_data['old_city'],
        'geo_api_infot': old_data['geo_api_infot'],
        'date': datetime.datetime.now(tz=pytz_timezone("Asia/Shanghai")).strftime("%Y-%m-%d"),
        # 近14日未离京
        # 'fjsj': old_data['fjsj'],  # 返京时间# 2021.8.1 del
        # 'ljrq': old_data['ljrq'],  # 离京日期 add@2021.1.24# 2021.8.1 del
        # 'qwhd': old_data['qwhd'],  # 去往何地 add@2021.1.24# 2021.8.1 del
        # 'chdfj': old_data['chdfj'],  # 从何地返京 add@2021.1.24# 2021.8.1 del

        # 'jcbhrq': old_data['jcbhrq'], # del 2021.1.29 接触病患日期
        # 'glksrq': old_data['glksrq'], # del 2021.1.29 隔离开始日期
        # 'fxyy': old_data['fxyy'],# 2021.8.1 del
        # 'jcjg': old_data['jcjg'],# 2021.8.1 del
        # 'jcjgt': old_data['jcjgt'],# 2021.8.1 del
        # 'qksm': old_data['qksm'],# 2021.8.1 del
        # 'remark': old_data['remark'],
        'jcjgqk': old_data['jcjgqk'],  #情况
        'jrsflj': old_data['jrsflj'],  # add @2020.9.16 近日是否离京
        # 'jcwhryfs': old_data['jcwhryfs'],# 2021.8.1 del
        # 'jchbryfs': old_data['jchbryfs'],# 2021.8.1 del
        'gtshcyjkzt': old_data['gtshcyjkzt'],  # add @2020.9.16 共同生活人员健康状况
        'jrsfdgzgfxdq': old_data['jrsfdgzgfxdq'],  # add @2020.9.16 近日是否到过中高风险地区
        'app_id': 'ucas'
    }

    if old_data["jrsflj"]!="否" :
        raise RuntimeError(f'近日是否离京不为否。请暂停后手动打卡！')

    return new_data

def display_time_formatted():
    # Return human-readable date with current display timezone, regardless of the host's timezone settings
    return datetime.datetime.now(tz=pytz_timezone(DISPLAY_TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S.%f')
