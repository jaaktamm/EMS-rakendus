"""Local server-rendered UI; one worker owns the search session and its lock."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import sys

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException, MultiPartParser

from .linguistics import analyzer
from .search import check_limit, search_session, validate_text
from .search_index import ensure_index
from .storage import EMSDataError, prepare

LOGGER = logging.getLogger('uvicorn.error')
HERE = Path(__file__).resolve().parent
MATCH_NAMES = {'exact':'Täpne algkuju','lemma':'Lemmafraas','prefix':'Sõna algus'}
RELATION_NAMES = {'broad':'Laiemad','narrow':'Kitsamad','related':'Seotud','unknown':'Muud seosed'}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_input_bytes: int = 5242880
    source_xml: Path | None = None
    source_metadata: Path | None = None

    @classmethod
    def environment(cls):
        size=int(os.environ.get('EMS_MAX_INPUT_BYTES','5242880'))
        if size<1:
            raise ValueError('EMS_MAX_INPUT_BYTES peab olema positiivne täisarv.')
        return cls(Path(os.environ.get('EMS_DATA_DIR','data')),size,
                   Path(os.environ['EMS_SOURCE_XML']) if os.environ.get('EMS_SOURCE_XML') else None,
                   Path(os.environ['EMS_SOURCE_META']) if os.environ.get('EMS_SOURCE_META') else None)


class Runtime:
    def __init__(self,settings):
        self.settings=settings
        self.context=None
        self.engine=None

    def start(self):
        LOGGER.info('EMS: kohalike andmete kontroll; puuduva baasi ettevalmistamine võib võtta mitu minutit.')
        base=prepare(self.settings.data_dir,self.settings.source_xml,self.settings.source_metadata)
        LOGGER.info('EMS: alusbaas %s.',base['action'])
        index=ensure_index(self.settings.data_dir,progress=True)
        LOGGER.info('EMS: otsingubaas %s.',index['action'])
        self.context=search_session(self.settings.data_dir)
        try:
            self.engine=self.context.__enter__()
            analyzer().analyze('See on proov.')  # Warm the one process-local analyzer.
        except BaseException:
            if self.engine is not None:
                self.context.__exit__(*sys.exc_info())
            self.engine=None
            self.context=None
            raise
        LOGGER.info('EMS: valmis päringuteks.')
        return {'base_action':base['action'],'index_action':index['action']}

    def stop(self):
        if self.context is not None:
            self.context.__exit__(None,None,None)
            self.context=None
            self.engine=None

    def lookup(self,query,mode,language,limit):
        return self.engine.lookup(query,mode,language,limit)

    def keywords(self,text,limit):
        return self.engine.keywords(text,limit)


class RequestLimit:
    """Bound total body bytes before multipart parsing, including chunked requests."""
    def __init__(self,app,maximum):
        self.app=app
        self.maximum=maximum

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in ('POST','PUT','PATCH'):
            await self.app(scope,receive,send)
            return
        headers=dict(scope.get('headers',[]))
        try:
            declared=int(headers.get(b'content-length',b'0'))
            if declared<0:
                raise ValueError
        except ValueError:
            await self.error(scope,receive,send,400,'Vigane päringu suurus.')
            return
        if declared>self.maximum:
            await self.error(scope,receive,send,413,'Päring on liiga suur. Vähenda teksti või faili mahtu.')
            return
        body=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect':
                return
            body.extend(message.get('body',b''))
            if len(body)>self.maximum:
                await self.error(scope,receive,send,413,'Päring on liiga suur. Vähenda teksti või faili mahtu.')
                return
            if not message.get('more_body',False):
                break
        sent=False
        async def replay():
            nonlocal sent
            if not sent:
                sent=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)

    @staticmethod
    async def error(scope,receive,send,status,message):
        response=HTMLResponse('<!doctype html><html lang="et"><meta charset="utf-8">'
            '<title>Sisendi viga · EMS</title><h1>Sisendi viga</h1><p>'+message+
            '</p><p><a href="/keywords">Tagasi märksõnastamise juurde</a></p></html>',
            status_code=status,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        await response(scope,receive,send)


async def form_data(request,maximum):
    if request.headers.get('content-type','').lower().startswith('multipart/form-data'):
        parser=MultiPartParser(request.headers,request.stream(),max_files=1,max_fields=6,max_part_size=maximum)
        # The outer body limit guarantees accepted uploads fit in memory, not a disk spool.
        parser.spool_max_size=maximum+65537
        try:
            return await parser.parse()
        except MultiPartException as exc:
            raise EMSDataError('Vigane vorm või liiga suur sisend. Saada üks tekst või üks .txt fail.') from exc
    return await request.form(max_files=1,max_fields=6,max_part_size=maximum)


def safe_ems_url(value):
    return value if value and re.fullmatch(r'https://ems[.]elnet[.]ee/id/EMS[0-9]+',value) else None


def validate_size(text,maximum):
    if len(text.encode('utf-8'))>maximum:
        raise EMSDataError(f'Tekst ületab lubatud mahu ({maximum} baiti).')
    validate_text(text)


def parsed_limit(value):
    try:
        limit=int(value)
    except (TypeError,ValueError) as exc:
        raise EMSDataError('Tulemuste ülempiir peab olema täisarv 1 kuni 50.') from exc
    check_limit(limit)
    return limit


def create_app(settings=None):
    settings=settings or Settings.environment()
    templates=Jinja2Templates(directory=str(HERE/'templates'))
    templates.env.filters['ems_url']=safe_ems_url

    @asynccontextmanager
    async def lifespan(app):
        executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ems-search')
        runtime=Runtime(settings)
        app.state.ready=False
        app.state.executor=executor
        app.state.runtime=runtime
        try:
            app.state.startup=await asyncio.get_running_loop().run_in_executor(executor,runtime.start)
            app.state.ready=True
            yield
        finally:
            app.state.ready=False
            await asyncio.get_running_loop().run_in_executor(executor,runtime.stop)
            executor.shutdown(wait=True)

    app=FastAPI(title='EMS-i kohalik otsing',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(RequestLimit,maximum=settings.max_input_bytes+65536)
    app.mount('/static',StaticFiles(directory=str(HERE/'static')),name='static')

    @app.middleware('http')
    async def response_headers(request,call_next):
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    def render(request,view,*,error=None,result=None,values=None,status=200,filename=None):
        return templates.TemplateResponse(request=request,name='page.html',status_code=status,context={
            'view':view,'error':error,'result':result,'values':values or {},'filename':filename,
            'maximum':settings.max_input_bytes,'match_names':MATCH_NAMES,'relation_names':RELATION_NAMES})

    @app.get('/')
    async def home():
        return RedirectResponse('/search',status_code=303)

    @app.get('/health')
    async def health(request:Request):
        ready=getattr(app.state,'ready',False)
        return JSONResponse({'status':'ready' if ready else 'starting'},status_code=200 if ready else 503)

    @app.get('/search',response_class=HTMLResponse)
    async def search_form(request:Request):
        return render(request,'search')

    @app.get('/keywords',response_class=HTMLResponse)
    async def keyword_form(request:Request):
        return render(request,'keywords')

    @app.post('/search',response_class=HTMLResponse)
    async def search_results(request:Request):
        form=None
        values={}
        try:
            form=await form_data(request,settings.max_input_bytes)
            if any(len(form.getlist(k))!=1 for k in form) or any(isinstance(v,UploadFile) for v in form.values()):
                raise EMSDataError('Vigane otsinguvorm.')
            values={k:str(form.get(k,'')) for k in ('query','mode','language','limit')}
            limit=parsed_limit(values['limit'] or '10')
            validate_size(values['query'],settings.max_input_bytes)
            mode=values['mode'] or 'all'
            language=values['language'] or 'all'
            result=await asyncio.get_running_loop().run_in_executor(app.state.executor,
                app.state.runtime.lookup,values['query'],mode,language,limit)
            return render(request,'search',result=result,values=values)
        except (EMSDataError,HTTPException,UnicodeError):
            exc=sys.exc_info()[1]
            message=str(exc) if isinstance(exc,EMSDataError) else 'Vigane vorm või kodeering.'
            return render(request,'search',error=message,values=values,status=400)
        finally:
            if form is not None:
                await form.close()

    @app.post('/keywords',response_class=HTMLResponse)
    async def keyword_results(request:Request):
        form=None
        values={}
        filename=None
        try:
            form=await form_data(request,settings.max_input_bytes)
            if any(len(form.getlist(k))!=1 for k in form):
                raise EMSDataError('Iga vormivälja võib saata ainult ühe korra.')
            if isinstance(form.get('text'),UploadFile) or isinstance(form.get('limit'),UploadFile):
                raise EMSDataError('Vigane tekstivorm.')
            values={'text':str(form.get('text','')),'limit':str(form.get('limit','10'))}
            limit=parsed_limit(values['limit'])
            upload=form.get('file')
            has_file=isinstance(upload,UploadFile) and bool(upload.filename)
            if values['text'].strip() and has_file:
                raise EMSDataError('Vali üks sisend: tekstikast või .txt fail, mitte mõlemad.')
            if has_file:
                filename=upload.filename
                if Path(filename).suffix.lower()!='.txt':
                    raise EMSDataError('Laadi üles .txt laiendiga UTF-8 tekstifail.')
                raw=await upload.read(settings.max_input_bytes+1)
                if len(raw)>settings.max_input_bytes:
                    raise EMSDataError(f'Fail ületab lubatud mahu ({settings.max_input_bytes} baiti).')
                try:
                    text=raw.decode('utf-8-sig')
                except UnicodeDecodeError as exc:
                    raise EMSDataError('Fail peab olema UTF-8 või UTF-8 BOM kodeeringus.') from exc
            else:
                text=values['text']
            validate_size(text,settings.max_input_bytes)
            result=await asyncio.get_running_loop().run_in_executor(app.state.executor,app.state.runtime.keywords,text,limit)
            return render(request,'keywords',result=result,values=values,filename=filename)
        except (EMSDataError,HTTPException,UnicodeError):
            exc=sys.exc_info()[1]
            message=str(exc) if isinstance(exc,EMSDataError) else 'Vigane vorm või kodeering.'
            return render(request,'keywords',error=message,values=values,status=400,filename=filename)
        finally:
            if form is not None:
                await form.close()

    return app


app=create_app()
