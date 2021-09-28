# This python file aims to trim audio files to create outputs
# with the required audio activity. 
# The audio file is first amplified to reduce noise and enhance
# audio activity for easier detection.
# The locations of the detected frames from the enhanced input
# will then be mapped to the original audio files, and be extracted.

import os
import argparse
import numpy as np

# To trim noise
from auditok import AudioRegion
# To amplify voice
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.utils import mediainfo
from logmmse import logmmse_from_file

# this function takes in a path (string) to an wav audio file.
# the input audio will be passed into a log-mmse filter to reduce noise.
# The output audio will then be normalized. 
# A temporary output file will be generated.
# The function returns the path to the temporary output wav file.

def enhance_audio(path):
    # noise reduction with log-mmse
    amp = logmmse_from_file(path)
    
    # get rate, channels of file
    info = mediainfo(path)
    rate, channels = int(info['sample_rate']), int(info['channels']) 
    
    # create AudioSegment of amplified audio
    audio_segment = AudioSegment(
        amp.tostring(), #amp.tobytes() 
        frame_rate=rate,
        sample_width=amp.dtype.itemsize, 
        channels=channels
    )
    
    # set channel to 1
    audio_segment = audio_segment.set_channels(1)
    
    # normalize the amplitude
    normed = normalize(audio_segment)
    
    temp_path = path[:-4] + '_tmp.wav'
    normed.export(temp_path, format='wav')
    
    return temp_path

# this function extracts the start and end frame of detected 
# audio activity from the enhanced input.
# the locations of the start and end frame will be extracted.
# It then maps the locations to the original audio input, and extract
# the voice activity from the original audio input.

def extract(path, out_path=None, max_dur=30, max_silence=1.5, eth=55, drop_trailing_silence=True):

    # set output filepath
    if out_path == None:
        out_path = path[:-4] + '_out.wav'

    # pass audio input into enhancer
    temp_path = enhance_audio(path)
    # Load enhanced input
    temp_region = AudioRegion.load(temp_path)
    # Split enhanced input into regions (audio slices with no silences)
    temp_regions = temp_region.split(
        max_dur=max_dur, 
        max_silence=max_silence, 
        eth=eth, 
        drop_trailing_silence=drop_trailing_silence
        )
    # Assume the first slice is the required output, extract start+end
    try: 
        selected_region = list(temp_regions)[0]
    except IndexError:
        print('Index Error raised. List index out of range.')
        print('Please check file at path: ', path)
        return 0

    start, end = selected_region.meta.start, selected_region.meta.end
    
    # Map start+end location to original input, and output the slice
    region = AudioRegion.load(path)
    final_region = region.seconds[start:end]
    final_region.save(out_path, audio_format='wav')

    # Remove temp audio
    os.remove(temp_path)
    
    return final_region

# this function simply runs the extract function
# over an entire directory

def extract_dir(dir_path, out_dir_path, suffix='_out', verbose=0, max_dur=30, max_silence=1.5, eth=55, drop_trailing_silence=True):
    
    # make output directory if doesn't exist
    if not os.path.exists(out_dir_path):
        os.makedirs(out_dir_path)

    # error list
    errors = []

    # retrieve only wav files in input directory
    files = os.listdir(dir_path)
    wav_files = list(filter(lambda x: x[-4:] == '.wav', files))
    num_wav_files = len(wav_files)

    print('Processing {} wav files...'.format(num_wav_files))
    for ind, wav_file in enumerate(wav_files):
        if verbose and (ind+1) % verbose == 0:
            print('{}/{} files processed.'.format(ind+1, num_wav_files))
        out_wav_file = wav_file[:-4] + suffix + '.wav'
        result = extract(os.path.join(dir_path, wav_file), os.path.join(out_dir_path, out_wav_file))

        # Append errors if spotted
        if result == 0:
            errors.append(os.path.join(dir_path, wav_file))

    print('Processing completed. {} files have been saved to: {}'.format(len(os.listdir(out_dir_path)), out_dir_path))

    if len(errors) > 0:
        error_filepath = os.path.join(dir_path, 'errors.txt')
        with open(error_filepath, 'w') as f:
            for error in errors:
                f.write('%s\n' % error)
        print('{} erroroneous files have been identified. Please refer to the file: {}'.format(len(errors), error_filepath))

def _extract(args):
    return extract(args.filename, out_path=args.out, max_dur=args.max_dur, max_silence=args.max_silence, eth=args.eth, drop_trailing_silence=args.dtl)

def _extract_dir(args):
    return extract_dir(args.dirname, args.out, suffix=args.suffix, verbose=args.verbose, max_dur=args.max_dur, max_silence=args.max_silence, eth=args.eth, drop_trailing_silence=args.dtl)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Trim noises')
    subparsers = parser.add_subparsers(help='sub-command help')

    # Commands for single wav file
    wav_parser = subparsers.add_parser('wav', help='Trim single wav file')
    wav_parser.add_argument('filename', help='Path to wav file')
    wav_parser.add_argument('--out', default=None, required=False, help='Path to output file')
    wav_parser.add_argument('--max_dur', default=30, type=int, required=False, help='Max duration of non-silence before new region slice')
    wav_parser.add_argument('--max_silence', default=1.5, type=int, required=False, help='Max silence before cutting out of the slice')
    wav_parser.add_argument('--eth', default=55, type=int, required=False, help='Energy threshold to determine silence')
    wav_parser.add_argument('--dtl', default=True, type=bool, required=False, help='Drop trailing silence')
    wav_parser.set_defaults(func=_extract)

    # Commands for entire directory
    dir_parser = subparsers.add_parser('dir', help='Trim all wav files in target directory')
    dir_parser.add_argument('dirname', help='Path to directory')
    dir_parser.add_argument('out', help='Path to output directory')
    dir_parser.add_argument('--suffix', default='_out', type=str, required=False, help='Add suffix to end of output wav file')
    dir_parser.add_argument('--verbose', default=0, type=int, required=False, help='Informs user of every x files processed')
    dir_parser.add_argument('--max_dur', default=30, type=int, required=False, help='Max duration of non-silence before new region slice')
    dir_parser.add_argument('--max_silence', default=1.5, type=int, required=False, help='Max silence before cutting out of the slice')
    dir_parser.add_argument('--eth', default=55, type=int, required=False, help='Energy threshold to determine silence')
    dir_parser.add_argument('--dtl', default=True, type=bool, required=False, help='Drop trailing silence')
    dir_parser.set_defaults(func=_extract_dir)

    args = parser.parse_args()
    args.func(args)