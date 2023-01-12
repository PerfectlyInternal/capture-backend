import api
from capture import arducam as ac
from webrtc import streamer, video

AC_FRAME_SIZE = (640, 480) # default arducam frame size
AC_FRAME_RATE = 60 # default arducam frame rate
AC_CFG = "to be implemented" # default arducam config file

def init():
    init_http_server()
    ac_manager = ac.ArduCamManager()

    # create 2 arducam streams, one for each eye
    ac_sources = []
    ac_devices = ac_manager.get_devices()
    logger.debug(f"ACam manager init done, following devices found: {ac_manager.get_devices()}")

    if(len(ac_devices) < 2): # if there arent 2 devices available, create 2 default devices which will probably fail to capture and return blank images
        ac_sources.append(ac.ArduCamSource(0, AC_FRAME_SIZE, AC_FRAME_RATE, AC_CFG))
        ac_sources.append(ac.ArduCamSource(1, AC_FRAME_SIZE, AC_FRAME_RATE, AC_CFG))
    else: # open first 2 devices 
        ac_sources.append(ac.ArduCamSource(devices[0, 0], AC_FRAME_SIZE, AC_FRAME_RATE, AC_CFG))
        ac_sources.append(ac.ArduCamSource(devices[1, 0], AC_FRAME_SIZE, AC_FRAME_RATE, AC_CFG))

    ac_tracks = []
    for source in ac_tracks:
        def create_ac_track():
            track = video.VideoStreamTrack(AC_FRAME_RATE)
            track.node(source.capture_frame)
            return track

        ac_tracks.append(streamer.MediaStreamTrackFactory(create_ac_track))

def init_http_server():
    pass


