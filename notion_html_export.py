#! /usr/bin/env python3
import sys
import time
import logging
import argparse
from tzlocal import get_localzone

import tqdm
import requests

logger = logging.getLogger("notion_export")


class _Connector:
    def __init__(self, token_v2, session=None):
        self._token_v2 = token_v2
        self._base_url = "https://www.notion.so"

        if session:
            self._session = session
        else:
            self._session = requests.Session()
            self._session.headers["cookie"] = "token_v2=%s" % self._token_v2

    def url_join(self, url):
        return self._base_url + url

    def normalize_block_id(self, block_id):
        without_dashes = "".join([x for x in block_id if x != "-"])
        correctly_formatted = "%s-%s-%s-%s-%s" % (
            without_dashes[0:8],
            without_dashes[8:12],
            without_dashes[12:16],
            without_dashes[16:20],
            without_dashes[20:],
        )
        return correctly_formatted


class Task(_Connector):
    def __init__(self, task_id, session, verbose=False):
        super().__init__("", session)
        self.task_id = task_id

        self.status = "unknown"
        self.result_dict = {}

        self.failed = False
        self.download_link = None
        self.is_exported = False
        self.in_progress = True

    def update(self):
        self.result_dict = self._download_task_status()
        self.task_dict = self._filter_task_with_id(self.result_dict)
        self.status = self.task_dict["state"].lower()

        if self.status == "in_progress":
            self.failed = False
            self.in_progress = True
            self.is_exported = False

            if "status" in self.task_dict:
                logger.info("Export in progress. Exported pages: %s", self.task_dict["status"]["pagesExported"])

        elif self.status == "success":
            self.failed = False
            self.in_progress = False
            self.is_exported = True

            self.download_link = self.task_dict["status"]["exportURL"]

            logger.info("Exported finished, downloading now ..")

        else:
            self.failed = True
            self.in_progress = False
            self.is_exported = False

    def _download_task_status(self):
        resp = self._session.post(self.url_join("/api/v3/getTasks"),
                                  json={"taskIds": [self.task_id]})

        # {"results": [{"id": "XXXXX", "eventName": "exportBlock",
        #               "request": {"blockId": "XXXXXX", "recursive": true,
        #                           "exportOptions": {"exportType": "html", "timeZone": "Europe/Prague",
        #                                             "locale": "en"}},
        #               "actor": {"table": "notion_user", "id": "XXXXX"},
        #               "state": "success", "rootRequest": {"eventName": "exportBlock",
        #                                                   "requestId": "XXXXX"},
        #               "status": {"type": "complete", "pagesExported": 1,
        #                          "exportURL": "https://s3.us-west-2.amazonaws.com/..."}}]}
        return resp.json()

    def _filter_task_with_id(self, result_dict):
        for task in result_dict["results"]:
            if task["id"] == self.task_id:
                return task

        raise ValueError("Task not found in results.")


class NotionExporter(_Connector):
    def __init__(self, token_v2):
        super().__init__(token_v2)

    def export_and_download(self, block_id):
        block_id = self.normalize_block_id(block_id)
        url = self.export(block_id)

        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            chunk_size = 65535
            download_len = int(r.headers["Content-Length"]) / chunk_size
            with open("Export-%s.zip" % block_id, 'wb') as f:
                for chunk in tqdm.tqdm(r.iter_content(chunk_size=chunk_size), total=download_len):
                    f.write(chunk)

    def export(self, block_id, callback_fn=None):
        block_id = self.normalize_block_id(block_id)
        task = self._enqueue_export_task(block_id)

        while True:
            task.update()

            if task.in_progress:
                time.sleep(5)
                continue

            if task.is_exported:
                if callback_fn is not None:
                    callback_fn(task.download_link)

                return task.download_link

            else:
                raise ValueError("Task wasn't successfully completed: %s" % task.result_dict)

    def _enqueue_export_task(self, block_id: str) -> Task:
        data = {"task": {"eventName": "exportBlock",
                         "request": {
                             "blockId": block_id,
                             "recursive": True,
                             "exportOptions": {
                                 "exportType": "html",
                                 "timeZone": get_localzone().zone,
                                 "locale": "en"}}}}

        resp = self._session.post(self.url_join("/api/v3/enqueueTask"), json=data)
        resp.raise_for_status()

        # {"taskId":"XXXXXXX"}
        result = resp.json()
        task_id = result["taskId"]

        logger.info("Task queued as `%s`.", task_id)

        return Task(task_id, self._session)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--token",
        required=True,
        help="`token_v2` value from cookies."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Be verbose."
    )
    parser.add_argument(
        "BLOCK_ID",
        help="Id of the block you want to export."
    )

    args = parser.parse_args()

    if args.verbose:
        stderr_logger = logging.StreamHandler(sys.stderr)
        log_fmt = ("\033[90m%(asctime)s %(levelname)s %(filename)s:%(lineno)s;\033[0m\n"
                   "%(message)s\n")
        stderr_logger.setFormatter(logging.Formatter(log_fmt))
        logger.addHandler(stderr_logger)
        logger.setLevel(logging.DEBUG)

    exporter = NotionExporter(args.token)
    exporter.export_and_download(args.BLOCK_ID)
