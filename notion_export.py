import argparse
import time

import requests


def export(block_id, callback_fn=None):
    session = requests.Session()
    session.headers[        "cookie"] = ""

    task_id = _enqueue_export_task(session, block_id)

    while True:
        result_dict, state = _get_task_status(session, task_id)

        if state == "in_progress":
            time.sleep(5)
            continue

        elif state == "success":
            result_url =
            if callback_fn is not None:
                callback_fn()

        else:
            raise ValueError("Task wasn't successfully completed: %s" % result_dict)


def _get_task_status(session, task_id):
    resp = session.post("https://www.notion.so/api/v3/getTasks",
                        data={"taskIds": [task_id]})

    # {"results": [{"id": "XXXXXXXX, "eventName": "exportBlock",
    #               "request": {"blockId": "XXXXXXXXX", "recursive": true,
    #                           "exportOptions": {"exportType": "html", "timeZone": "Europe/Prague",
    #                                             "locale": "en"}},
    #               "actor": {"table": "notion_user", "id": "XXXXXXX"},
    #               "state": "in_progress", "rootRequest": {"eventName": "exportBlock",
    #                                                       "requestId": "XXXXX"}}]}
    result_dict = resp.json()
    state = result_dict["results"][0]["state"]

    return result_dict, state


def _enqueue_export_task(session, block_id):
    data = {"task": {"eventName": "exportBlock",
                     "request": {
                         "blockId": block_id,
                         "recursive": True,
                         "exportOptions": {
                             "exportType": "html",
                             "timeZone": "Europe/Prague",
                             "locale": "en"}}}}
    resp = session.post("https://notion.so/api/v3/enqueueTask", data=data)

    # {"taskId":"XXXXXXX"}
    result = resp.json()
    task_id = result["taskId"]

    return task_id


def _parse_download_url(result_dict):
    # {"results": [{"id": "XXXXX", "eventName": "exportBlock",
    #               "request": {"blockId": "XXXXXX", "recursive": true,
    #                           "exportOptions": {"exportType": "html", "timeZone": "Europe/Prague",
    #                                             "locale": "en"}},
    #               "actor": {"table": "notion_user", "id": "XXXXX"},
    #               "state": "success", "rootRequest": {"eventName": "exportBlock",
    #                                                   "requestId": "XXXXX"},
    #               "status": {"type": "complete", "pagesExported": 1,
    #                          "exportURL": "https://s3.us-west-2.amazonaws.com/..."}}]}
    return result_dict["results"][0]["status"]["exportURL"]


if __name__ == '__main__':
    export(block_id="05d803fa-a527-4e3d-8581-51c25df951ed")
