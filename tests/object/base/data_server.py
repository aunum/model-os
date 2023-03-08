# This file was generated by ModelOS
import json
import logging
import os
import typing
from typing import List

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute, Route

from modelos.object.encoding import deep_isinstance, is_first_order

from .base_test import Data, Ham

log_level = os.getenv("LOG_LEVEL")
if log_level is None:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=log_level)


class DataServer(Data):
    """A resource server for Data"""

    async def _get_d_req(self, request):
        """Request for function:
        get_d(self, name: str) -> __main__.Ham
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.get_d(**_jdict)
        print("called function: ", _ret)
        # code for object: <class '__main__.Ham'>
        _ret = _ret.__dict__  # type: ignore
        # end object: <class '__main__.Ham'>

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _get_h_req(self, request):
        """Request for function:
        get_h(self) -> __main__.Ham
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.get_h(**_jdict)
        print("called function: ", _ret)
        # code for object: <class '__main__.Ham'>
        _ret = _ret.__dict__  # type: ignore
        # end object: <class '__main__.Ham'>

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _get_lh_req(self, request):
        """Request for function:
        get_lh(self) -> List[__main__.Ham]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.get_lh(**_jdict)
        print("called function: ", _ret)
        # code for list: typing.List[__main__.Ham]
        _ret_list = []
        for _a_val in _ret:  # type: ignore
            # code for object: <class '__main__.Ham'>
            _a_val = _a_val.__dict__  # type: ignore
            # end object: <class '__main__.Ham'>

            _ret_list.append(_a_val)
        _ret = _ret_list
        # end list: typing.List[__main__.Ham]

        _ret = {"value": _ret}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _get_o_req(self, request):
        """Request for function:
        get_o(self) -> Optional[__main__.Ham]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.get_o(**_jdict)
        print("called function: ", _ret)
        # code for union: typing.Optional[__main__.Ham]
        if deep_isinstance(_ret, None):
            pass
        elif deep_isinstance(_ret, Ham):
            # code for object: <class '__main__.Ham'>
            _ret = _ret.__dict__  # type: ignore
            # end object: <class '__main__.Ham'>

        else:
            raise ValueError(
                "Do not know how to serialize"
                + "parameter 'typing.Optional[__main__.Ham]' "
                + f"of type '{type(_ret)}'"
            )
        # end union: typing.Optional[__main__.Ham]

        if is_first_order(type(_ret)) or _ret is None:
            _ret = {"value": _ret}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _get_u_req(self, request):
        """Request for function:
        get_u(self) -> Union[str, __main__.Ham]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.get_u(**_jdict)
        print("called function: ", _ret)
        # code for union: typing.Union[str, __main__.Ham]
        if deep_isinstance(_ret, str):
            pass
        elif deep_isinstance(_ret, Ham):
            # code for object: <class '__main__.Ham'>
            _ret = _ret.__dict__  # type: ignore
            # end object: <class '__main__.Ham'>

        else:
            raise ValueError(
                "Do not know how to serialize"
                + "parameter 'typing.Union[str, __main__.Ham]' "
                + f"of type '{type(_ret)}'"
            )
        # end union: typing.Union[str, __main__.Ham]

        if is_first_order(type(_ret)) or _ret is None:
            _ret = {"value": _ret}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _health_req(self, request):
        """Request for function:
        health(self) -> Dict[str, str]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        print("calling function: ", _jdict)
        _ret = self.health(**_jdict)
        print("called function: ", _ret)

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _info_req(self, request):
        """Request for function:
        info(self) -> modelos.object.kind.ObjectInfo
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        print("calling function: ", _jdict)
        _ret = self.info(**_jdict)
        print("called function: ", _ret)
        # code for object: <class 'modelos.object.kind.ObjectInfo'>
        _ret = _ret.__dict__  # type: ignore
        _ext: typing.Optional[typing.Dict[str, str]] = _ret["ext"]
        # code for union: typing.Optional[typing.Dict[str, str]]
        if deep_isinstance(_ext, None):
            pass
        elif deep_isinstance(_ext, typing.Dict[str, str]):
            pass
        else:
            raise ValueError(
                "Do not know how to serialize"
                + "parameter 'typing.Optional[typing.Dict[str, str]]' "
                + f"of type '{type(_ext)}'"
            )
        # end union: typing.Optional[typing.Dict[str, str]]

        _ret["ext"] = _ext
        # end object: <class 'modelos.object.kind.ObjectInfo'>

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _lock_req(self, request):
        """Request for function:
        lock(self, key: Optional[str] = None, timeout: Optional[int] = None) -> None  # noqa
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        if "key" in _jdict:
            _key = _jdict["key"]
            # code for union: typing.Optional[str]
            if _key is None:
                pass
            elif type(_key) == str:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: key - type: {type(_key)}"
                )
            # end union: typing.Optional[str]

            _jdict["key"] = _key
        if "timeout" in _jdict:
            _timeout = _jdict["timeout"]
            # code for union: typing.Optional[int]
            if _timeout is None:
                pass
            elif type(_timeout) == int:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: timeout - type: {type(_timeout)}"
                )
            # end union: typing.Optional[int]

            _jdict["timeout"] = _timeout

        print("calling function: ", _jdict)
        _ret = self.lock(**_jdict)
        print("called function: ", _ret)
        _ret = {"value": None}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _save_req(self, request):
        """Request for function:
        save(self, out_dir: str = './artifacts') -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.save(**_jdict)
        print("called function: ", _ret)
        _ret = {"value": None}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _set_d_req(self, request):
        """Request for function:
        set_d(self, name: str, ham: __main__.Ham) -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        _ham = _jdict["ham"]

        # code for obj: Ham
        _ham_obj = object.__new__(Ham)
        _a_attr = _ham["a"]
        setattr(_ham_obj, "a", _a_attr)

        _b_attr = _ham["b"]
        setattr(_ham_obj, "b", _b_attr)

        _ham = _ham_obj  # type: ignore
        # end obj: Ham

        _jdict["ham"] = _ham

        print("calling function: ", _jdict)
        _ret = self.set_d(**_jdict)
        print("called function: ", _ret)
        _ret = {"value": None}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _unlock_req(self, request):
        """Request for function:
        unlock(self, key: Optional[str] = None, force: bool = False) -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        if "key" in _jdict:
            _key = _jdict["key"]
            # code for union: typing.Optional[str]
            if _key is None:
                pass
            elif type(_key) == str:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: key - type: {type(_key)}"
                )
            # end union: typing.Optional[str]

            _jdict["key"] = _key

        print("calling function: ", _jdict)
        _ret = self.unlock(**_jdict)
        print("called function: ", _ret)
        _ret = {"value": None}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _labels_req(self, request):
        """Request for function:
        labels() -> Dict[str, str]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.labels(**_jdict)
        print("called function: ", _ret)

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _name_req(self, request):
        """Request for function:
        name() -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.name(**_jdict)
        print("called function: ", _ret)
        _ret = {"value": _ret}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    async def _short_name_req(self, request):
        """Request for function:
        short_name() -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.short_name(**_jdict)
        print("called function: ", _ret)
        _ret = {"value": _ret}

        print("returning: ", _ret)
        return JSONResponse(_ret)

    def _routes(self) -> List[BaseRoute]:
        return [
            Route("/get_d", endpoint=self._get_d_req, methods=["POST"]),
            Route("/get_h", endpoint=self._get_h_req, methods=["POST"]),
            Route("/get_lh", endpoint=self._get_lh_req, methods=["POST"]),
            Route("/get_o", endpoint=self._get_o_req, methods=["POST"]),
            Route("/get_u", endpoint=self._get_u_req, methods=["POST"]),
            Route("/health", endpoint=self._health_req, methods=["GET", "POST"]),
            Route("/info", endpoint=self._info_req, methods=["POST"]),
            Route("/lock", endpoint=self._lock_req, methods=["POST"]),
            Route("/save", endpoint=self._save_req, methods=["POST"]),
            Route("/set_d", endpoint=self._set_d_req, methods=["POST"]),
            Route("/unlock", endpoint=self._unlock_req, methods=["POST"]),
            Route("/labels", endpoint=self._labels_req, methods=["POST"]),
            Route("/name", endpoint=self._name_req, methods=["POST"]),
            Route("/short_name", endpoint=self._short_name_req, methods=["POST"]),
        ]


o = DataServer.from_env()
pkgs = o._reload_dirs()

app = Starlette(routes=o._routes())

if __name__ == "__main__":
    logging.info(f"starting server version '{o.scm.sha()}' on port: 8080")
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        workers=1,
        reload=True,
        reload_dirs=pkgs.keys(),
    )