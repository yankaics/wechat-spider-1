# -*- coding: utf-8 -*-
'''
Created on 2017-09-22 15:55
---------
@summary:
---------
@author: Boris
'''
import sys
sys.path.append('..')

import collections

from utils.log import log
import utils.tools as tools
import web
import json
import random
from service.wechat_service import WechatService


MIN_SLEEP_TIME = 10000 # 每个历史列表、文章详情时间间隔  毫秒
MAX_SLEEP_TIME = 15000
WAIT_TIME = 1000 * 60 * 60 # 做完所有公众号后休息的时间，然后做下一轮
# WAIT_TIME = 25000

class WechatAction():
    _todo_urls = collections.deque() # 待做的url

    _article_info = { # 缓存文章信息，第一次缓存列表信息、第二次缓存观看量点赞量，第三次直到评论信息也取到后，则入库
        "article_id":{
            "title":"",
            "content":"",
            #....
        }
    }

    _account_info = { # 用来缓存__biz 和 account_id的对应信息
        # '__biz' : 'account_id'
    }


    def __init__(self):
        self._wechat_service = WechatService()

        self._is_need_get_more = True # 是否需要获取更多文章。 当库中该条文章存在时，不需要获取更早的文章，默认库中已存在。如今天的文章库中已经存在了，如果爬虫一直在工作，说明昨天的文章也已经入库，增量试

    def get_sleep_time(self):
        return random.randint(MIN_SLEEP_TIME, MAX_SLEEP_TIME)

    def __open_next_page(self):
        '''
        @summary: 跳转到历史文章
        ---------
        @param __biz:
        @param pass_ticket:
        @param appmsg_token:
        @param offset:
        ---------
        @result:
        '''
        is_done = False # 是否做完一轮

        if WechatAction._todo_urls:
            url = WechatAction._todo_urls.popleft()
        else:
            # 跳转到下一个公众号
            account_id, __biz, is_done = self._wechat_service.get_next_account()
            WechatAction._account_info[__biz] = account_id or ''

            # url = 'http://mp.weixin.qq.com/mp/getmasssendmsg?__biz=%s#wechat_webview_type=1&wechat_redirect'%__biz
            url = 'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=%s&scene=124#wechat_redirect'%__biz
            log.debug('''
                下一个公众号 ： %s
                '''%url)
        log.debug('''
            next_page_url : %s
            is_done:        %s
            '''%(url, is_done))

        # 注入js脚本实现自动跳转
        next_page = "<script>setTimeout(function(){window.location.href='%s';},%d);</script>"%(url, self.get_sleep_time() if not is_done else WAIT_TIME)
        return next_page

    def __parse_account_info(self, data, req_url):
        '''
        @summary:
        ---------
        @param data:
        ---------
        @result:
        '''
        __biz = tools.get_param(req_url, '__biz')

        regex = 'id="nickname">(.*?)</strong>'
        account = tools.get_info(data, regex, fetch_one = True).strip()

        regex = 'profile_avatar">.*?<img src="(.*?)"'
        head_url = tools.get_info(data, regex, fetch_one = True)

        regex = 'class="profile_desc">(.*?)</p>'
        summary = tools.get_info(data, regex, fetch_one = True).strip()

        # 认证信息（关注的账号直接点击查看历史消息，无认证信息）
        regex = '<i class="icon_verify success">.*?</i>(.*?)</span>'
        verify = tools.get_info(data, regex, fetch_one = True)
        verify = verify.strip() if verify else ''

        # 二维码
        regex = 'var username = "" \|\| "(.*?)";' # ||  需要转译
        qr_code = tools.get_info(data, regex, fetch_one = True)
        qr_code = 'http://open.weixin.qq.com/qr/code?username=' + qr_code

        account_info = {
            '__biz' : __biz,
            'account' : account,
            'head_url' : head_url,
            'summary' : summary,
            'qr_code' : qr_code,
            'verify' : verify,
            'account_id' : WechatAction._account_info.pop(__biz) if __biz in WechatAction._account_info.keys() else '',
            'record_time' : tools.get_current_date()
        }

        if not self._wechat_service.is_exist('wechat_account', __biz):
            self._wechat_service.add_account_info(account_info)

    def __parse_article_list(self, article_list):
        '''
        @summary: 解析文章列表
        ---------
        @param article_list: 文章列表信息 str
        {
            "list":[
                {
                    "comm_msg_info":{
                        "id":1000000513,
                        "type":49,
                        "datetime":1511354167,
                        "fakeid":"3082125093",
                        "status":2,
                        "content":""
                    },
                    "app_msg_ext_info":{
                        "title":"Python 内存优化",
                        "digest":"实际项目中，pythoner更加关注的是Python的性能问题。本文，关注的是Python的内存优化，一般说来，如果不发生内存泄露，运行在服务端的Python代码不用太关心内存，但是如果运行在客户端，那还是有优化的必要。",
                        "content":"",
                        "fileid":505083208,
                        "content_url":"http:\/\/mp.weixin.qq.com\/s?__biz=MzA4MjEyNTA5Mw==&amp;mid=2652566858&amp;idx=1&amp;sn=d2a76f4a601f94d8acc7b436d18e9648&amp;chksm=8464dd00b313541684c14f974325ea6ae725ffc901fd9888cc00d1acdd13619de3297a5d9a35&amp;scene=27#wechat_redirect",
                        "source_url":"http:\/\/www.cnblogs.com\/xybaby\/p\/7488216.html",
                        "cover":"http:\/\/mmbiz.qpic.cn\/mmbiz_jpg\/fhujzoQe7TpODTuicia4geCiaIj1AbZwVQQVbRHy3FhzwMHEvCvtzXVicHTaPEu8jZ2pgkCAgBqEHugYMvzg3tpoww\/0?wx_fmt=jpeg",
                        "subtype":9,
                        "is_multi":1,
                        "multi_app_msg_item_list":[
                            {
                                "title":"面向对象：With the wonder of your love, the sun above always shines",
                                "digest":"With the wonder of your love, the sun above always shines",
                                "content":"",
                                "fileid":505083209,
                                "content_url":"http:\/\/mp.weixin.qq.com\/s?__biz=MzA4MjEyNTA5Mw==&amp;mid=2652566858&amp;idx=2&amp;sn=97f223783da7748080f8103654447c99&amp;chksm=8464dd00b313541601938565a41487ea76209331fd6f4c8996a2ff5572f4fd465de9fa4cbaac&amp;scene=27#wechat_redirect",
                                "source_url":"https:\/\/mp.weixin.qq.com\/s\/_uD9jY4nXQQ6CtA__dsN8w?scene=25#wechat_redirect",
                                "cover":"http:\/\/mmbiz.qpic.cn\/mmbiz_jpg\/fhujzoQe7TpODTuicia4geCiaIj1AbZwVQQ5ukvwH1GPq5zlWxv05WvRiaw6BiaeyGRD1w17nAPGTlQgEvvDuZnB9HA\/0?wx_fmt=jpeg",
                                "author":"",
                                "copyright_stat":101,
                                "del_flag":1
                            }
                        ],
                        "author":"",
                        "copyright_stat":100,
                        "del_flag":1
                    }
                }
            ]
        }
        ---------
        @result:
        '''
        log.debug(tools.dumps_json(article_list))

        # 解析json内容里文章信息
        def parse_article_info(article_info, release_time):
            if not article_info:
                return

            # log.debug(tools.dumps_json(article_info))
            title = article_info.get('title')
            summary = article_info.get('digest')
            url = article_info.get('content_url').replace('\\', '').replace('amp;', '')
            source_url = article_info.get('source_url').replace('\\', '')  # 引用的文章链接
            cover = article_info.get('cover').replace('\\', '')
            author = article_info.get('author')
            if url: # 被发布者删除的文章 无url和其他信息， 此时取不到mid 且不用入库
                mid = tools.get_param(url, 'mid') or tools.get_param(url, 'appmsgid') # 图文消息id 同一天发布的图文消息 id一样
                idx = tools.get_param(url, 'idx') or tools.get_param(url, 'itemidx')# 第几条图文消息 从1开始
                article_id = mid + idx # 用mid和idx 拼接 确定唯一一篇文章 如mid = 2650492260  idx = 1，则article_id = 26504922601

                # 判断该文章库中是否已存在
                if self._wechat_service.is_exist('wechat_article', article_id):
                    self._is_need_get_more  = False
                    return # 不往下进行 舍弃之后的文章

                __biz = tools.get_param(url, '__biz') # 用于关联公众号

                # 缓存文章信息
                WechatAction._article_info[article_id] = {
                    'article_id':int(article_id),
                    'title' : title,
                    'summary' : summary,
                    'release_time':release_time,
                    'url' : url,
                    'source_url' : source_url,
                    'cover' : cover,
                    'account':'',
                    'author' : author,
                    '__biz' : __biz,
                    'read_num' : 'null',
                    'like_num' : 'null',
                    'content' : '',
                    'comment' : [],
                    'record_time':tools.get_current_date()
                }

                # 将文章url添加到待抓取队列
                WechatAction._todo_urls.append(url)

        # log.debug(tools.dumps_json(article_list))
        article_list = tools.get_json(article_list)

        article_list = article_list.get('list', [])
        for article in article_list:
            article_type = article.get('comm_msg_info', {}).get('type')
            if article_type != 49: # 49为常见的图文消息、其他消息有文本、语音、视频，此处不采集，格式不统一
                continue

            release_time = article.get('comm_msg_info', {}).get('datetime')
            release_time = tools.timestamp_to_date(release_time)

            # 微信公众号每次可以发多个图文消息
            # 第一个图文消息
            app_msg_ext_info = article.get('app_msg_ext_info', {})
            parse_article_info(app_msg_ext_info, release_time)

            if not self._is_need_get_more:
                break

            # 同一天附带的图文消息
            multi_app_msg_item_list = app_msg_ext_info.get('multi_app_msg_item_list')
            for multi_app_msg_item in multi_app_msg_item_list:
                parse_article_info(multi_app_msg_item, release_time)

                if not self._is_need_get_more:
                    break

    def get_article_list(self, data, req_url):
        '''
        @summary: 获取文章列表
        分为两种
            1、第一次查看历史消息 返回的是html格式 包含公众号信息
            2、下拉显示更多时 返回json格式
        但是文章列表都是json格式 且合适相同
        抓取思路：
        1、如果是第一种格式，直接解析文章内容，拼接下一页json格式的地址
        2、如果是第二种格式，
        ---------
        @param data:
        ---------
        @result:
        '''
        try:
            # 判断是否为被封的账号， 被封账号没有文章列表
            if 'list' in data:
                # 取html格式里的文章列表
                if 'action=home' in req_url:
                    # 解析公众号信息
                    self.__parse_account_info(data, req_url)

                    # 解析文章列表
                    regex = "msgList = '(.*?})';"
                    article_list = tools.get_info(data, regex, fetch_one = True)
                    article_list = article_list.replace('&quot;', '"')
                    self.__parse_article_list(article_list)

                    #判断是否还有更多文章 没有跳转到下个公众号，有则下拉显示更多
                    regex = "can_msg_continue = '(\d)'"
                    can_msg_continue = tools.get_info(data, regex, fetch_one = True)
                    if can_msg_continue == '0':# 无更多文章
                        pass
                    elif self._is_need_get_more:
                        # 以下是拼接下拉显示更多的历史文章 跳转
                        # 取appmsg_token 在html中
                        regex = 'appmsg_token = "(.*?)";'
                        appmsg_token = tools.get_info(data, regex, fetch_one = True)

                        # 取其他参数  在url中
                        __biz = tools.get_param(req_url, '__biz')
                        pass_ticket = tools.get_param(req_url, 'pass_ticket')

                        next_page_url = 'https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={__biz}&f=json&offset={offset}&count=10&is_ok=1&scene=124&uin=777&key=777&pass_ticket={pass_ticket}&wxtoken=&appmsg_token={appmsg_token}&x5=0&f=json'.format(__biz = __biz, offset = 10, pass_ticket = pass_ticket, appmsg_token = appmsg_token)
                        WechatAction._todo_urls.append(next_page_url)

                else:# json格式
                    data = tools.get_json(data)
                    article_list = data.get('general_msg_list', {})
                    self.__parse_article_list(article_list)

                    #判断是否还有更多文章 没有跳转到下个公众号，有则下拉显示更多
                    can_msg_continue = data.get('can_msg_continue')
                    if not can_msg_continue: # 无更多文章
                        pass
                    elif self._is_need_get_more:
                        # 以下是拼接下拉显示更多的历史文章 跳转
                        # 取参数  在url中
                        __biz = tools.get_param(req_url, '__biz')
                        pass_ticket = tools.get_param(req_url, 'pass_ticket')
                        appmsg_token = tools.get_param(req_url, 'appmsg_token')

                        # 取offset 在json中
                        offset = data.get('next_offset', 0)

                        next_page_url = 'https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={__biz}&f=json&offset={offset}&count=10&is_ok=1&scene=124&uin=777&key=777&pass_ticket={pass_ticket}&wxtoken=&appmsg_token={appmsg_token}&x5=0&f=json'.format(__biz = __biz, offset = offset, pass_ticket = pass_ticket, appmsg_token = appmsg_token)
                        WechatAction._todo_urls.append(next_page_url)

            else: # 该__biz 账号已被封
                pass
        except Exception as e:
            log.error(e)

        return self.__open_next_page()

    def get_article_content(self, data, req_url):
        log.debug('获取文章内容')

        if data: # 被验证不详实的文章 首次不反回内容，跳转到https://mp.weixin.qq.com/mp/rumor
            req_url = req_url.replace('amp;', '')
            mid = tools.get_param(req_url, 'mid') or tools.get_param(req_url, 'appmsgid') # 图文消息id 同一天发布的图文消息 id一样
            idx = tools.get_param(req_url, 'idx') or tools.get_param(req_url, 'itemidx') # 第几条图文消息 从1开始
            article_id = mid + idx # 用mid和idx 拼接 确定唯一一篇文章 如mid = 2650492260  idx = 1，则article_id = 26504922601

            regex = '(<div class="rich_media_content " id="js_content">.*?)<script nonce'
            content = tools.get_info(data, regex, fetch_one = True)
            if content:
                # 缓存文章内容
                WechatAction._article_info[article_id]['content'] = content
                # 取公众号名
                regex = '<span class="rich_media_meta rich_media_meta_text rich_media_meta_nickname">(.*?)</span>'
                account = tools.get_info(data, regex, fetch_one = True)
                WechatAction._article_info[article_id]['account'] = account

            else: # 被验证不实的文章，不会请求观看点赞数，此时直接入库
                regex = '<title>(.*?)</title>'
                content = tools.get_info(data, regex, fetch_one = True)
                WechatAction._article_info[article_id]['content'] = content

                # 入库
                self._wechat_service.add_article_info(WechatAction._article_info.pop(article_id))

            # 如果下一页是文章列表的链接， 替换文章列表中的appmsg_token,防止列表链接过期
            if (len(WechatAction._todo_urls) == 1) and ('/mp/profile_ext' in WechatAction._todo_urls[-1]):
                regex = 'appmsg_token = "(.*?)"'
                appmsg_token = tools.get_info(data, regex, fetch_one = True).strip()

                WechatAction._todo_urls[-1] =  tools.replace_str(WechatAction._todo_urls[-1], 'appmsg_token=.*?&', 'appmsg_token=%s&'%appmsg_token)

            return self.__open_next_page()

        else:
            # 无文章内容
            pass

    def get_read_watched_count(self, data, req_url):
        '''
        @summary:
        ---------
        @param data:
        {
            "advertisement_num":0,
            "advertisement_info":[

            ],
            "appmsgstat":{
                "show":true,
                "is_login":true,
                "liked":false,
                "read_num":38785,
                "like_num":99,
                "ret":0,
                "real_read_num":0
            },
            "comment_enabled":1,
            "reward_head_imgs":[

            ],
            "only_fans_can_comment":false,
            "is_ios_reward_open":0,
            "base_resp":{
                "wxtoken":3465907592
            }
        }
        @param req_url:
        ---------
        @result:
        '''

        log.debug('获取观看和点赞量')

        req_url = req_url.replace('amp;', '')

        mid = tools.get_param(req_url, 'mid') # 图文消息id 同一天发布的图文消息 id一样
        idx = tools.get_param(req_url, 'idx') # 第几条图文消息 从1开始
        article_id = mid + idx # 用mid和idx 拼接 确定唯一一篇文章 如mid = 2650492260  idx = 1，则article_id = 26504922601

        data = tools.get_json(data)
        read_num = data.get('appmsgstat', {}).get('read_num')
        like_num = data.get('appmsgstat', {}).get('like_num')

        # 缓存文章阅读量点赞量
        WechatAction._article_info[article_id]['read_num'] = read_num
        WechatAction._article_info[article_id]['like_num'] = like_num

        if not data.get('comment_enabled'): # 无评论区，不请求get_comment 函数，此时直接入库
            self._wechat_service.add_article_info(WechatAction._article_info.pop(article_id))


    def get_comment(self, data, req_url):
        log.debug('获取评论信息')

        req_url = req_url.replace('amp;', '')
        mid = tools.get_param(req_url, 'appmsgid') # 图文消息id 同一天发布的图文消息 id一样
        idx = tools.get_param(req_url, 'idx') # 第几条图文消息 从1开始
        article_id = mid + idx # 用mid和idx 拼接 确定唯一一篇文章 如mid = 2650492260  idx = 1，则article_id = 26504922601

        data = tools.get_json(data)
        comment = data.get('elected_comment', []) # 精选留言

        # 缓存文章评论信息
        WechatAction._article_info[article_id]['comment'] = comment

        self._wechat_service.add_article_info(WechatAction._article_info.pop(article_id))

    def deal_request(self, name):
        web.header('Content-Type','text/html;charset=UTF-8')

        data_json = json.loads(json.dumps(web.input()))
        data = data_json.get('data') # data为str
        req_url = data_json.get('req_url')

        # log.debug('''
        #     method : %s
        #     data   ：%s
        #     '''%(name, data))

        log.debug('''
            method : %s
            url   ：%s
            '''%(name, req_url))

        reponse = ''
        if name == 'get_article_list':
            reponse = self.get_article_list(data, req_url)

        elif name == 'get_article_content':
            reponse = self.get_article_content(data, req_url)

        elif name == 'get_read_watched_count':
            reponse = self.get_read_watched_count(data, req_url)

        elif name == 'get_comment':
            reponse = self.get_comment(data, req_url)

        # log.debug('''
        #     ---------reponse---------
        #     %s'''%reponse)

        return reponse # 此处返回''空字符串  不会触发node-js http 的回调

    def GET(self, name):
        return self.deal_request(name)

    def POST(self, name):
        return self.deal_request(name)


if __name__ == '__main__':
    wechat_action = WechatAction()
    sleep_time = wechat_action.get_sleep_time()
    print(sleep_time)