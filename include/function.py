import re
from typing import Dict, Optional
import logging
import requests
import datetime
from pytz import timezone as pytz_timezone
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

    # app_id = 4
    # new_data = {
    #     'realname': old_data['realname'],
    #     'number': old_data['number'],
    #     'szgj_api_info': old_data['szgj_api_info'],
    #     'sfzx': old_data['sfzx'], #是否在校
    #     'szdd': '国内', #所在地点 update 2022.2.9
    #     'ismoved': 0,  # 如果前一天位置变化这个值会为1，第二天仍然获取到昨天的1，而事实上位置是没变化的，所以置0
    #     'tw': old_data['tw'], #体温
    #     'sfcxtz': old_data['sfcxtz'], #todo 是否出现症状
    #     'sfjcbh': old_data['sfjcbh'],  # 是否接触病患
    #     'sfcyglq': old_data['sfcyglq'],  # 是否处于隔离期（观察期
    #     'sfcxzysx': old_data['sfcxzysx'], #
    #     'geo_api_info': old_data['old_city'],  # 保持昨天的结果
    #     'old_city': old_data['old_city'],
    #     'geo_api_infot': old_data['geo_api_infot'],
    #     'date': datetime.datetime.now(tz=pytz_timezone("Asia/Shanghai")).strftime("%Y-%m-%d"),
    #     'jcjgqk': old_data['jcjgqk'],  #情况
    #     'jrsflj': old_data['jrsflj'],  # add @2020.9.16 近日是否离京
    #     'gtshcyjkzt': old_data['gtshcyjkzt'],  # add @2020.9.16 共同生活人员健康状况
    #     'jrsfdgzgfxdq': old_data['jrsfdgzgfxdq'],  # add @2020.9.16 近日是否到过中高风险地区
    #     'app_id': 'ucas'
    # }
    # if old_data["jrsflj"]!="否" :
    # raise RuntimeError(f'近日是否离京不为否。请暂停后手动打卡！')

    # app_id = 9
    new_data = {
        'date': datetime.datetime.now(tz=pytz_timezone("Asia/Shanghai")).strftime("%Y-%m-%d"),
        'realname': old_data['realname'],
        'number': old_data['number'],
        'jzdz': old_data['jzdz'],  # 居住地址
        'zrzsdd': old_data['zrzsdd'],  # 昨日居住地点
        # todo: add new db column for 今日是否在校
        'sfzx': 5,  # 是否在校
        'dqszdd': old_data['dqszdd'],  # 当前所在地点
        'geo_api_infot': old_data['geo_api_infot'],  # 保持昨天的结果
        'szgj': old_data['szgj'],  # 所在国家
        'szgj_select_info[id]': 0,  # 所在国家
        'szgj_select_info[name]': '',  # 所在国家
        'geo_api_info': old_data['old_city'],  # 保持昨天的结果
        'dqsfzzgfxdq': old_data['dqsfzzgfxdq'],  # 当前是否在中高风险地区
        'zgfxljs': old_data['zgfxljs'],  # 中高风险旅居史
        'tw': '1',  # 体温，不是1就完蛋了
        'sffrzz': '0',  # 是否发热症状
        'dqqk1': 1,  # 当前情况状态
        'dqqk1qt':  '',  # 当前情况其他
        'dqqk2': 1,  # 当前情况健康码
        'dqqk2qt':  '',  # 当前情况其他
        # todo: add new db column for 昨日是否接受核酸检测
        'sfjshsjc': 0,  # （昨日）是否接受核酸检测
        'dyzymjzqk': old_data['dyzymjzqk'],  # 第一针疫苗接种情况
        'dyzwjzyy':  old_data['dyzwjzyy'],  # 第一帧未接种原因
        'dyzjzsj': old_data['dyzjzsj'],  # 第一帧疫苗接种时间
        'dezymjzqk': old_data['dezymjzqk'],  # 第二针疫苗接种情况
        'dezwjzyy': old_data['dezwjzyy'],  # 第二帧未接种原因
        'dezjzsj': old_data['dezjzsj'],  # 第二帧疫苗接种时间
        'dszymjzqk': old_data['dszymjzqk'],  # 第三针疫苗接种情况
        'dszwjzyy': old_data['dszwjzyy'],  # 第三帧未接种原因
        'dszjzsj': old_data['dszjzsj'],  # 第三帧疫苗接种时间
        'gtshryjkzk': old_data['gtshryjkzk'],  # 共同生活人员健康情况
        'extinfo': '',  # 扩展信息
        'app_id': 'ucas'
    }

    return new_data


def display_time_formatted():
    # Return human-readable date with current display timezone, regardless of the host's timezone settings
    return datetime.datetime.now(tz=pytz_timezone(DISPLAY_TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S.%f')
