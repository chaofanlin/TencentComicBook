import argparse
import os
import logging

from .comicbook import ComicBook
from .crawlerbase import CrawlerBase
from .image_cache import image_cache
from .utils import parser_chapter_str
from .utils.mail import Mail
from . import VERSION

logger = logging.getLogger(__name__)


def parse_args():
    """
    根据腾讯漫画id下载图片,默认下载海贼王最新一集。

    下载海贼王最新一集:
    python3 onepiece.py

    下载漫画 id=505430 最新一集:
    python3 onepiece.py -id 505430

    下载漫画 id=505430 所有章节:
    python3 onepiece.py -id 505430 -m all

    下载漫画 id=505430 第800集:
    python3 onepiece.py -id 505430 -c 800

    下载漫画 id=505430 倒数第二集:
    python3 onepiece.py -id 505430 -c -2

    下载漫画 id=505430 1到5集,7集，9到10集:
    python3 onepiece.py -id 505430 -i 1-5,7,9-10
    """

    parser = argparse.ArgumentParser(prog="onepiece")

    parser.add_argument('-id', '--comicid', type=str,
                        help="漫画id，海贼王: 505430 (http://ac.qq.com/Comic/ComicInfo/id/505430)")

    parser.add_argument('--name', type=str, help="漫画名")

    parser.add_argument('-c', '--chapter', type=str, default="-1",
                        help="要下载的章节, 默认下载最新章节。如 -c 666 或者 -c 1-5,7,9-10")

    parser.add_argument('--worker', type=int, default=4, help="线程池数，默认开启4个线程池")

    parser.add_argument('--all', action='store_true',
                        help="是否下载该漫画的所有章节, 如 --all")

    parser.add_argument('--pdf', action='store_true',
                        help="是否生成pdf文件, 如 --pdf")

    parser.add_argument('--login', action='store_true',
                        help="是否登录账号，如 --login")

    parser.add_argument('--mail', action='store_true',
                        help="是否发送pdf文件到邮箱, 如 --mail。需要预先配置邮件信息。\
                        可以参照config.ini.example文件，创建并修改config.ini文件")

    parser.add_argument('--config', default="config.ini",
                        help="配置文件路径，默认取当前目录下的config.ini")

    parser.add_argument('-o', '--output', type=str, default='./download',
                        help="文件保存路径，默认保存在当前路径下的download文件夹")
    support_site = ComicBook.CRAWLER_CLS_MAP.keys()
    parser.add_argument('--site', type=str, default='qq', choices=support_site,
                        help="数据源网站：支持{}".format(','.join(sorted(support_site))))

    parser.add_argument('--cachedir', type=str, default='./.cache',
                        help="图片缓存目录，默认为当前目录下.cache")

    parser.add_argument('--nocache', action='store_true',
                        help="禁用图片缓存")

    parser.add_argument('--noverify', action='store_true',
                        help="noverify")

    parser.add_argument('--driver-path', type=str, help="selenium driver")

    parser.add_argument('--driver-type', type=str,
                        choices=CrawlerBase.SUPPORT_DRIVER_TYPE,
                        help="支持的浏览器: {}. 默认为 {}".format(
                            ",".join(sorted(CrawlerBase.SUPPORT_DRIVER_TYPE)),
                            CrawlerBase.DEFAULT_DRIVER_TYPE)
                        )

    parser.add_argument('--session-path', type=str, help="读取或保存上次使用的session路径")

    parser.add_argument('-V', '--version', action='version', version=VERSION)
    parser.add_argument('--debug', action='store_true', help="debug")

    args = parser.parse_args()
    return args


def init_logger(level=None):
    level = level or logging.INFO
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(name)s [%(levelname)s] %(message)s",
        datefmt='%Y/%m/%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def main():
    args = parse_args()

    site = args.site
    comicid = args.comicid
    output_dir = args.output
    is_download_all = args.all
    is_send_mail = args.mail
    is_gen_pdf = args.pdf
    is_login = args.login
    session_path = None
    if args.session_path:
        session_path = os.path.abspath(args.session_path)
    loglevel = logging.DEBUG if args.debug else logging.INFO
    init_logger(level=loglevel)

    if args.mail:
        Mail.init(args.config)
    if args.noverify:
        image_cache.set_verify(verify=False)

    image_cache.DEFAULT_POOL_SIZE = args.worker
    image_cache.IS_USE_CACHE = False if args.nocache else True
    image_cache.set_cache_dir(args.cachedir)

    default_comicid = {
        "qq": "505430",  # 海贼王
        "u17": "195",    # 雏蜂
        "bilibili": "mc24742",   # 海贼王
    }
    comicid = comicid or default_comicid.get(site)
    comicbook = ComicBook.create_comicbook(site=site, comicid=comicid)
    comicbook.crawler.DRIVER_PATH = args.driver_path
    # 加载 session
    if session_path and os.path.exists(session_path):
        comicbook.crawler.load_session(session_path)

    if args.name:
        result = comicbook.search(site=args.site, name=args.name, limit=10)
        for item in result:
            print("name={}\tcomicid={}\tsource_url={}".format(item.name, item.comicid, item.source_url))
        comicid = input("请输入要下载的comicid: ")
        comicbook.crawler.comicid = comicid

    logger.info("正在获取最新数据")

    if is_login:
        comicbook.crawler.login()

    comicbook.start_crawler()
    msg = ("{source_name} 【{name}】 更新至: {last_chapter_number:>03} "
           "【{last_chapter_title}】 数据来源: {source_url}").format(
        source_name=comicbook.source_name,
        name=comicbook.name,
        last_chapter_number=comicbook.last_chapter_number,
        last_chapter_title=comicbook.last_chapter_title,
        source_url=comicbook.source_url)
    logger.info(msg)
    chapter_number_list = parser_chapter_str(chapter_str=args.chapter,
                                             last_chapter_number=comicbook.last_chapter_number,
                                             is_all=is_download_all)

    for chapter_number in chapter_number_list:
        try:
            chapter = comicbook.Chapter(chapter_number)
            logger.info("正在下载 【{}】 {} 【{}】".format(
                comicbook.name, chapter.chapter_number, chapter.title))
            if is_gen_pdf or is_send_mail:
                pdf_path = chapter.save_as_pdf(output_dir=output_dir)
                if is_send_mail:
                    Mail.send(subject=os.path.basename(pdf_path),
                              content=None,
                              file_list=[pdf_path, ])
                logger.info("下载成功 %s", pdf_path)
            else:
                chapter_dir = chapter.save(output_dir=output_dir)
                logger.info("下载成功  %s", chapter_dir)
        except Exception as e:
            logger.exception(e)

    # 保存 session
    if session_path:
        os.makedirs(os.path.dirname(session_path), exist_ok=True)
        comicbook.crawler.export_session(session_path)
        logger.info("session保存在: {}".format(session_path))

    image_cache.auto_clean()


if __name__ == '__main__':
    main()
