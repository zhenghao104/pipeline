import json
import logging
import os
import pdb
import traceback
from concurrent import futures
import grpc
import pipeline_pb2
import pipeline_pb2_grpc
from config import settings
from taskspec import pipeline
import taskspec.scheduler
from util.amend_mpd import amend_mpd
from util.media_probe import get_signed_URI

_server = None


class PipelineServer(pipeline_pb2_grpc.PipelineServicer):
    def Submit(self, request, context):
        logging.info('PipelineServer handling submit request')

        try:
            pipe = pipeline.create_from_spec(json.loads(request.pipeline_spec))

            for index in range(len(request.inputs)):
                configs = {}
                for k, v in pipe.stages.iteritems():
                    configs[k] = v.conf
                in_event = {'key': request.inputs[index].value,
                            'metadata': {'pipe_id': pipe.pipe_id, 'configs': configs, 'lineage': '0'}}
                pipe.inputs['input_' + str(index)]['dst_node'].put({request.inputs[index].type: in_event})
                # put events to the buffer queue of all input stages

            pipe_dir = 'logs/' + pipe.pipe_id
            os.system('mkdir -p ' + pipe_dir)

            handler = logging.FileHandler(pipe_dir + '/log.csv')
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter('%(created)f, %(message)s'))
            logger = logging.getLogger(pipe.pipe_id)
            logger.propagate = False
            logger.setLevel(logging.DEBUG)
            logger.addHandler(handler)

            logger.info('starting pipeline')
            sched = getattr(taskspec.scheduler, settings.get(settings['scheduler'], 'SimpleScheduler'))
            sched.schedule(pipe)
            logger.info('pipeline finished')

            result_queue = pipe.outputs.values()[0]['dst_node']  # should be only one output queue

            num_m4s = 0
            out_key = None
            logging.debug("length of output queue: %s", result_queue.qsize())

            while not result_queue.empty():
                chunk = result_queue.get(block=False)['chunks']  # TODO: should distinguish chunks vs. m4schunks
                num_m4s += 1
                if int(chunk['metadata']['lineage']) == 1:
                    out_key = chunk['key']

            logging.debug("number of m4s chunks: %s", num_m4s)
            if out_key is not None:
                os.system('aws s3 cp ' + out_key + '00000001_dash.mpd ' + pipe_dir + '/')
                logging.info('mpd downloaded')
                with open(pipe_dir + '/00000001_dash.mpd', 'r') as fin:
                    init_mpd = fin.read()

                final_mpd = amend_mpd(init_mpd, float(num_m4s), out_key, num_m4s)

                logging.info('mpd amended')
                with open(pipe_dir + '/output.xml', 'wb') as fout:
                    fout.write(final_mpd)

                os.system('aws s3 cp ' + pipe_dir + '/output.xml ' + out_key)
                logging.info('mpd uploaded')
                signed_mpd = get_signed_URI(out_key + 'output.xml')
                logging.info('mpd signed, returning')

                return pipeline_pb2.SubmitReply(success=True, mpd_url=signed_mpd)

            else:
                return pipeline_pb2.SubmitReply(success=False, error_msg='no output is found')

        except Exception as e:
            return pipeline_pb2.SubmitReply(success=False, error_msg=traceback.format_exc())


def serve():
    global _server
    _server = grpc.server(futures.ThreadPoolExecutor(max_workers=1000))
    pipeline_pb2_grpc.add_PipelineServicer_to_server(PipelineServer(), _server)
    _server.add_insecure_port('0.0.0.0:%d' % settings['daemon_port'])
    _server.start()


def stop(val):
    global _server
    _server.stop(val)