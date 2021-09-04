import os
import json
import re
import time
import datetime
import sqlite3
import configparser
from bs4 import BeautifulSoup
from requests_html import HTMLSession

class Telegram:
    def __init__(self):
      self.BASE_DIR = os.path.split(os.path.realpath(__file__))[0]
      config = configparser.ConfigParser()
      config.read(os.path.join(self.BASE_DIR, 'config.ini'), encoding='utf-8')
      self.TELEGRAM_BOT_TOKEN = config.get("TELEGRAM", "BOT_TOKEN")
      self.TELEGRAM_CHAT_ID = config.get("TELEGRAM", "CHAT_ID")
      proxy = config.get("TELEGRAM", "PROXY")
      self.PROXIES = {"http": proxy, "https": proxy}
      self.SESSION = HTMLSession()
      self.SESSION.adapters.DEFAULT_RETRIES = 5  # 增加重连次数
      self.SESSION.keep_alive = False  # 关闭多余连接

    def send(self, auth, text, link):
      """
      给电报发送文字消息
      """
      headers = { 'Content-Type': 'application/json' }
      data = {
        'chat_id': self.TELEGRAM_CHAT_ID,
        'text': f'*{auth}:* {text}',
        'parse_mode': 'Markdown',
        'reply_markup': {
          'inline_keyboard': [[{
            'text': '🔗点击查看链接',
            'url': link,
          }]]
        }
      }

      url = f'https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage'
      try:
        self.SESSION.post(url, headers=headers, data=json.dumps(data,ensure_ascii=False).encode('utf-8'), proxies=self.PROXIES)
      except:
        print('    |-网络代理错误')
        time.sleep(2)
        self.send(auth, text, link)

class Weibo:
  def __init__(self):
    self.BASE_DIR = os.path.split(os.path.realpath(__file__))[0]
    config = configparser.ConfigParser()
    config.read(os.path.join(self.BASE_DIR, 'config.ini'), encoding='utf-8')
    self.WEIBO_IDS = json.loads(config.get("WEIBO", "IDS"))
    self.SESSION = HTMLSession()
    self.SESSION.adapters.DEFAULT_RETRIES = 5  # 增加重连次数
    self.SESSION.keep_alive = False  # 关闭多余连接
    self.telegram = Telegram()

  def check(self, weibo):
    """
    检查当前微博是否已处理过，如果没处理过则发送博文以及配图到Telegram
    """
    # print(os.path.join(self.BASE_DIR, 'weibo.db'))
    conn = sqlite3.connect('sto.db')
    cursor = conn.cursor()

    try:
      create_tb_cmd='''
      CREATE TABLE IF NOT EXISTS weibo
      (id varchar(20),
      content TEXT,
      link TEXT,
      uid varchar(20),
      avatar TEXT,
      name TEXT)
      '''
      cursor.execute(create_tb_cmd)
    except:
      print('创建失败')
      
    sql = "SELECT COUNT(id) AS counts FROM weibo WHERE id = ?"
    print(weibo)
    cursor.execute(sql, (weibo['id'],))
    result = cursor.fetchone()

    if result[0] <= 0:

      self.telegram.send(
        weibo['name'],
        weibo['content'],
        weibo['link']
      )

      sql = "INSERT INTO weibo(id, content, link, uid, avatar, name) VALUES(?, ?, ?, ?, ?, ?)"
      cursor.execute(sql, (
        weibo['id'],
        weibo['content'],
        weibo['link'],
        weibo['uid'],
        weibo['avatar'],
        weibo['name']
      ))
      conn.commit()
      conn.close()

      return True
    else:
      return False

  def get(self, uid):
    print('get')
    url = f'https://m.weibo.cn/api/container/getIndex?containerid=107603{uid}'
    try:
      weibo_items = self.SESSION.get(url).json()['data']['cards'][::-1]
    except:
      print('    |-访问url出错了')

    for item in weibo_items:
      weibo = {}
      weibo['content'] = BeautifulSoup(item['mblog']['text'].replace('<br />', '\n'), 'html.parser').get_text()

      try:
        weibo['pics'] = [pic['large']['url'] for pic in item['mblog']['pics']]
      except:
        weibo['pics'] = []

      short_url = item['scheme']
      short_url = short_url[short_url.rindex('/') + 1:short_url.index('?')]
      weibo['id'] = item['mblog']['id']
      weibo['link'] = f'https://weibo.com/{uid}/{short_url}'
      weibo['uid'] = uid
      weibo['avatar'] = item['mblog']['user']['profile_image_url']
      weibo['name'] = item['mblog']['user']['screen_name']

      self.check(weibo)

  def run(self):
    print(time.strftime('%Y-%m-%d %H:%M:%S go!', time.localtime()))
    for id in self.WEIBO_IDS:
      self.get(id)

class Nga: 
  def __init__(self):
    self.BASE_DIR = os.path.split(os.path.realpath(__file__))[0]
    config = configparser.ConfigParser()
    config.read(os.path.join(self.BASE_DIR, 'config.ini'), encoding='utf-8')
    self.SESSION = HTMLSession()
    self.SESSION.cookies.set("ngaPassportUid", config.get("NGA", "UID"), domain=".nga.cn")
    self.SESSION.cookies.set("ngaPassportCid", config.get("NGA", "CID"), domain=".nga.cn")
    self.origin = config.get("NGA", "ORIGIN")
    self.users = json.loads(config.get("NGA", "USERS")) # nga用户信息
    self.postedReplyUsers = json.loads(config.get("NGA", "POSTED_REPLY_USERS")) # 需要搜索的已发布帖子的用户id
    self.telegram = Telegram()
  
  def run(self):
    if len(self.users) > 0:
      self.getReplyUsers()

  # 获取用户发言
  def getReplyUsers(self):
    # post = {'content': 'Reply Post by 禾戈禾戈 (2021-08-16 10:25):估值又被杀了，短期防御防御吧。杀估值那。。。利好三大成长赛道？', 'name': '板了，下班', 'uid': '63233842', 'id': 541747313, 'link': 'https://bbs.nga.cn/read.php?tid=24900465&pid=541747313'}
    # self.check(post)
    for authorid in self.postedReplyUsers:
      url = f'{self.origin}/thread.php?searchpost=1&authorid={authorid}&__output=11'
      try:
        list = self.SESSION.get(url).json()['data']['__T'][::-1]
        for item in list:
          name = self.users[authorid]
          post = {}
          pid = item['__P']['pid']
          tpcurl = item['tpcurl']
          post['content'] = BeautifulSoup(re.compile('\[.*?\]').sub('', item['__P']['content']).replace(r'\[.+\]', ''), 'html.parser').get_text()
          post['name'] = name
          post['uid'] = authorid
          post['id'] = pid
          post['link'] = f'{self.origin}{tpcurl}&pid={pid}'
          self.check(post)
      except:
        print('    |-访问url出错了')
  
  def check(self, item):
    conn = sqlite3.connect('sto.db')
    cursor = conn.cursor()

    try:
      create_tb_cmd='''
      CREATE TABLE IF NOT EXISTS nga
      (id varchar(20),
      content TEXT,
      link TEXT,
      uid varchar(20),
      name TEXT)
      '''
      cursor.execute(create_tb_cmd)
    except:
      print('创建失败')
      
    sql = "SELECT COUNT(id) AS counts FROM nga WHERE id = ?"
    print(item)
    cursor.execute(sql, (item['id'],))
    result = cursor.fetchone()

    if result[0] <= 0:
      self.telegram.send(
        item['name'],
        item['content'],
        item['link']
      )

      sql = "INSERT INTO nga(id, content, link, uid, name) VALUES(?, ?, ?, ?, ?)"
      cursor.execute(sql, (
        item['id'],
        item['content'],
        item['link'],
        item['uid'],
        item['name']
      ))
      conn.commit()
      conn.close()

      return True
    else:
      return False


if __name__ == '__main__':
  nga = Nga()
  weibo = Weibo()

  while True:
    now = datetime.datetime.now()
    h = now.hour
    w = now.weekday() + 1
    if h >= 9 and h < 15 and w >= 1 and w <= 5:
      nga.run()
      weibo.run()
    time.sleep(60)
  