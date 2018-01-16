import logging
import re
import queue as q
import pkg_resources

from volta.common.interfaces import Phone
from volta.common.util import execute, Drain, popen, LogReader, PhoneTestPerformer
from volta.common.resource import manager as resource


logger = logging.getLogger(__name__)


event_regexp = r"""
    ^
    (?P<date>\S+)
    \s+
    (?P<time>\S+)
    \s+
    (?P<tag>(\S+?)\s*\(\s*\d+\))
    :\s+
    (?P<message>.*)
    $
    """


class Abro(Phone):
    def __init__(self, config):
        Phone.__init__(self, config)
        self.logcat_stdout_reader = None
        self.logcat_stderr_reader = None
        self.source = config.get_option('phone', 'source', 'serial_number')
        self.blink = config.get_option('phone', 'blink', False)
        self.delay = config.get_option('phone', 'blink_delay', 0)
        self.toast = config.get_option('phone', 'blink_toast', False)
        self.led = config.get_option('phone', 'led', True)
        self.threads = config.get_option('phone', 'threads', 1)
        self.blinks = config.get_option('phone', 'blinks', 10)
        self.camera_manager = config.get_option('phone', 'camera_manager', False)
        self.regexp = config.get_option('phone', 'event_regexp', event_regexp)
        logger.debug(self.regexp)
        try:
            self.compiled_regexp = re.compile(self.regexp, re.VERBOSE | re.IGNORECASE)
        except:
            logger.debug('Unable to parse specified regexp', exc_info=True)
            raise RuntimeError("Unable to parse specified regexp")
        self.drain_logcat_stdout = None
        self.test_performer = None


    def prepare(self):
        execute("adb -s {device_id} logcat -c".format(device_id=self.source))


    def start(self, results):
        self.phone_q = results
        self.__start_async_logcat()
        if self.blink:
            cmd = "adb -s {device_id} shell am startservice -a BLINK --ei DELAY {delay} --ez TOAST {toast} --ez LED {led} --ei THREADS {threads} --ei BLINKS {blinks} --ez MGR {mgr} -n com.yandex.pma/.PmaIntentService".format(
                device_id = self.source,
                delay = self.delay,
                toast = self.toast,
                led = self.led,
                threads = self.threads,
                blinks = self.blinks,
                mgr = self.camera_manager
            )
            logger.info(cmd)
            execute(cmd)
        return


    def __start_async_logcat(self):
        cmd = "adb -s {device_id} logcat -v time".format(device_id=self.source)
        logger.debug("Execute : %s", cmd)
        self.logcat_process = popen(cmd)

        self.logcat_reader_stdout = LogReader(self.logcat_process.stdout, self.compiled_regexp)
        self.drain_logcat_stdout = Drain(self.logcat_reader_stdout, self.phone_q)
        self.drain_logcat_stdout.start()

        self.phone_q_err=q.Queue()
        self.logcat_reader_stderr = LogReader(self.logcat_process.stderr, self.compiled_regexp)
        self.drain_logcat_stderr = Drain(self.logcat_reader_stderr, self.phone_q_err)
        self.drain_logcat_stderr.start()


    def run_test(self):
        #logger.info('Infinite loop for volta because there are no tests specified, waiting for SIGINT')
        command = 'while [ 1 ]; do sleep 1; done'
        self.test_performer = PhoneTestPerformer(command)
        #self.test_performer.start()
        return


    def end(self):
        if self.test_performer:
            self.test_performer.close()
            #self.test_performer.join()
        self.logcat_reader_stdout.close()
        self.logcat_reader_stderr.close()
        self.logcat_process.kill()
        self.drain_logcat_stdout.close()
        logger.info('drain_logcat_stdout.join()')
        self.drain_logcat_stdout.join()
        self.drain_logcat_stderr.close()
        #self.drain_logcat_stderr.join()
        logger.info('abdo test ended')
        return


    def get_info(self):
        data = {}
        if self.drain_logcat_stdout:
            data['grabber_alive'] = self.drain_logcat_stdout.isAlive()
        if self.phone_q:
            data['grabber_queue_size'] = self.phone_q.qsize()
        if self.test_performer:
            data['test_performer_alive'] = self.test_performer.isAlive()
        return data
