import os
from scipy.io.wavfile import read
import scipy.io.wavfile as wav
import subprocess as sp
import numpy as np
import argparse
import random
import os
import sys
from random import shuffle
import speechpy
import datetime
import tables

######################################
####### Define the dataset class #####
######################################
class AudioDataset():
    """Audio dataset."""

    def __init__(self, files_path, audio_dir, transform=None):
        """
        Args:
            files_path (string): Path to the .txt file which the address of files are saved in it.
            root_dir (string): Directory with all the audio files.
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """

        # self.sound_files = [x.strip() for x in content]
        self.audio_dir = audio_dir
        self.transform = transform

        # Open the .txt file and create a list from each line.
        with open(files_path, 'r') as f:
            content = f.readlines()
        # you may also want to remove whitespace characters like `\n` at the end of each line
        list_files = []
        for x in content:
            sound_file_path = os.path.join(self.audio_dir, x.strip().split()[1])
            try:
                with open(sound_file_path, 'rb') as f:
                    riff_size, _ = wav._read_riff_chunk(f)
                    file_size = os.path.getsize(sound_file_path)

                # Assertion error.
                assert riff_size == file_size and os.path.getsize(sound_file_path) > 1000, "Bad file!"

                # Add to list if file is OK!
                if riff_size > 40000: #to omit small file
                    list_files.append(x.strip())
            except OSError as err:
                print("OS error: {0}".format(err))
            except ValueError:
                print('file %s is corrupted!' % sound_file_path)
            # except:
            #     print("Unexpected error:", sys.exc_info()[0])
            #     raise

        # Save the correct and healthy sound files to a list.
        self.sound_files = list_files

    def __len__(self):
        return len(self.sound_files)

    def __getitem__(self, idx):
        # Get the sound file path
        sound_file_path = os.path.join(self.audio_dir, self.sound_files[idx].split()[1])

        ##############################
        ### Reading and processing ###
        ##############################

        # Reading .wav file
        fs, signal = wav.read(sound_file_path)

        # Reading .wav file
        import soundfile as sf
        signal, fs = sf.read(sound_file_path)

        ###########################
        ### Feature Extraction ####
        ###########################

        # DEFAULTS:
        num_coefficient = 40

        # Staching frames
        frames = speechpy.processing.stack_frames(signal, sampling_frequency=fs, frame_length=0.025,
                                                  frame_stride=0.01,
                                                  zero_padding=True)

        # # Extracting power spectrum (choosing 3 seconds and elimination of DC)
        power_spectrum = speechpy.processing.power_spectrum(frames, fft_points=2 * num_coefficient)[:, 1:]

        logenergy = speechpy.feature.lmfe(signal, sampling_frequency=fs, frame_length=0.025, frame_stride=0.01,
                                          num_filters=num_coefficient, fft_length=1024, low_frequency=0,
                                          high_frequency=None)
        #print(logenergy.shape)

        ########################
        ### Handling sample ####
        ########################

        # Label extraction
        #label = int(self.sound_files[idx].split()[0])
        label = self.sound_files[idx].split()[0]

        sample = {'feature': logenergy, 'label': label}

        ########################
        ### Post Processing ####
        ########################
        if self.transform:
            sample = self.transform(sample)
        else:
            feature, label = sample['feature'], sample['label']
            sample = feature, label

        return sample
        # return sample


class CMVN(object):
    """Cepstral mean variance normalization.

    """

    def __call__(self, sample):
        feature, label = sample['feature'], sample['label']

        # Mean variance normalization of the spectrum.
        # The following line should be Uncommented if cepstral mean variance normalization is desired!
        # feature = speechpy.processing.cmvn(feature, variance_normalization=True)

        return {'feature': feature, 'label': label}

class Feature_Cube(object):
    """Return a feature cube of desired size.

    Args:
        cube_shape (tuple): The shape of the feature cube.
    """

    def __init__(self, cube_shape, augmentation=True):
        assert isinstance(cube_shape, (tuple))
        self.augmentation = augmentation
        self.cube_shape = cube_shape
        self.num_utterances = cube_shape[0]
        self.num_frames = cube_shape[1]
        self.num_coefficient = cube_shape[2]


    def __call__(self, sample):
        feature, label = sample['feature'], sample['label']

        # Feature cube.
        feature_cube = np.zeros((self.num_utterances, self.num_frames, self.num_coefficient), dtype=np.float32)

        if self.augmentation:
            # Get some random starting point for creation of the future cube of size (num_frames x num_coefficient x num_utterances)
            # Since we are doing random indexing, the data augmentation is done as well because in each iteration it returns another indexing!
            idx = np.random.randint(feature.shape[0] - self.num_frames, size=self.num_utterances)
            for num, index in enumerate(idx):
                feature_cube[num, :, :] = feature[index:index + self.num_frames, :]
        else:
            idx = range(self.num_utterances)
            for num, index in enumerate(idx):
                feature_cube[num, :, :] = feature[index:index + self.num_frames, :]


        #print(feature_cube)
        # return {'feature': feature_cube, 'label': label}
        return {'feature': feature_cube[None, :, :, :], 'label': label}


class ToOutput(object):
    """Return the output.

    """

    def __call__(self, sample):
        feature, label = sample['feature'], sample['label']

        feature, label = sample['feature'], sample['label']
        return feature, label

class Compose(object):
    """Composes several transforms together.
    Args:
        transforms (list of ``Transform`` objects): list of transforms to compose.
    Example:
        >>> Compose([
        >>>     CMVN(),
        >>>     Feature_Cube(cube_shape=(20, 80, 40),
        >>>     augmentation=True), ToOutput(),
        >>>        ])
        If necessary, for the details of this class, please refer to Pytorch documentation.
    """

    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, img):
        for t in self.transforms:
            img = t(img)
        return img

    def __repr__(self):
        format_string = self.__class__.__name__ + '('
        for t in self.transforms:
            format_string += '\n'
            format_string += '    {0}'.format(t)
        format_string += '\n)'
        return format_string

class data_saver():
    def __init__(self):
        pass

    @staticmethod
    def get_label_map():
        label_map = {}
        label_map_path = "./label_map"
        with open(label_map_path) as in_handler:
            for each_line in in_handler:
                each_line = each_line.strip()
                line_arr = each_line.split()
                label_map[line_arr[0]] = int(line_arr[1])
        return label_map

    @staticmethod
    def save_dev_v2(file_path):
        dataset = AudioDataset(files_path=file_path, audio_dir="",transform=Compose(
                                   [CMVN(), Feature_Cube(cube_shape=(20, 80, 40), augmentation=True), ToOutput()]))  # args.audio_dir,)

        # idx is the representation of the batch size which chosen to be as one sample (index) from the data.
        # ex: batch_features = [dataset.__getitem__(idx)[0] for idx in range(32)]
        # The batch_features is a list and len(batch_features)=32.

        feature_map = {}
        #for i in range(len(dataset)):
        #    feature,label =
        fileh = tables.open_file("./develpment_v2.hdf5", mode="w")
        filters = tables.Filters(complevel=5, complib="blosc")
        train_label_list = []
        utterance_train = fileh.create_earray("/", "utterance_train", tables.Atom.from_sctype(np.float32),
                                              shape=(0, 20, 80, 40),
                                              filters=filters)
        test_label_list = []
        utterance_test = fileh.create_earray("/", "utterance_test", tables.Atom.from_sctype(np.float32),
                                             shape=(0, 20, 80, 40),
                                             filters=filters)
        # utterance_earray.append(feature_list)
        label_index = 0
        label_map = data_saver.get_label_map()

        random.seed(123)
        for idx in range(len(dataset)):
            feature, label = dataset.__getitem__(idx)
            print(label, feature.shape)
            label_index = label_map[label]
            randint = random.randint(1, 10)
            if randint > 2:
                train_label_list.append(label_index)
                utterance_train.append(feature)
            else:
                test_label_list.append(label_index)
                utterance_test.append(feature)

        train_label_earray = fileh.create_earray("/", "label_train", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                 filters=filters)
        train_label_earray.append(train_label_list)

        test_label_earray = fileh.create_earray("/", "label_test", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                filters=filters)
        test_label_earray.append(test_label_list)

        # utterance_earray = fileh.create_earray("/", "utterance_train", tables.Atom.from_dtype(feature.dtype),shape=(0, feature.shape[1],feature.shape[2],feature.shape[3]), filters=filters)
        # utterance_earray.append(feature_list)
        # for x in range(feature.shape[0]):
        #    print(feature[x,].shape)
        #    utterance_earray.append(feature[x,])
        print(fileh)
        fileh.close()

    @staticmethod
    def save_dev(file_path):
        dataset = AudioDataset(files_path=file_path, audio_dir="",  # args.audio_dir,
                               transform=Compose(
                                   [CMVN(), Feature_Cube(cube_shape=(20, 80, 40), augmentation=True), ToOutput()]))

        # idx is the representation of the batch size which chosen to be as one sample (index) from the data.
        # ex: batch_features = [dataset.__getitem__(idx)[0] for idx in range(32)]
        # The batch_features is a list and len(batch_features)=32.
        fileh = tables.open_file("./dev.hdf5", mode="w")
        filters = tables.Filters(complevel=5, complib="blosc")
        train_label_list = []
        utterance_train = fileh.create_earray("/", "utterance_train", tables.Atom.from_sctype(np.float32),
                                              shape=(0, 20, 80, 40),
                                              filters=filters)
        test_label_list = []
        utterance_test = fileh.create_earray("/", "utterance_test", tables.Atom.from_sctype(np.float32),
                                             shape=(0, 20, 80, 40),
                                             filters=filters)
        # utterance_earray.append(feature_list)
        random.seed(123)
        for idx in range(len(dataset)):
            feature, label = dataset.__getitem__(idx)
            print(label, feature.shape)
            randint = random.randint(1, 10)
            if randint > 2:
                train_label_list.append(label)
                utterance_train.append(feature)
            else:
                test_label_list.append(label)
                utterance_test.append(feature)

        train_label_earray = fileh.create_earray("/", "label_train", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                 filters=filters)
        train_label_earray.append(train_label_list)

        test_label_earray = fileh.create_earray("/", "label_test", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                filters=filters)
        test_label_earray.append(test_label_list)

        # utterance_earray = fileh.create_earray("/", "utterance_train", tables.Atom.from_dtype(feature.dtype),shape=(0, feature.shape[1],feature.shape[2],feature.shape[3]), filters=filters)
        # utterance_earray.append(feature_list)
        # for x in range(feature.shape[0]):
        #    print(feature[x,].shape)
        #    utterance_earray.append(feature[x,])
        print(fileh)
        fileh.close()

    @staticmethod
    def save_enrollment(file_path):
        dataset = AudioDataset(files_path=file_path, audio_dir="",  # args.audio_dir,
                               transform=Compose(
                                   [CMVN(), Feature_Cube(cube_shape=(1, 80, 40), augmentation=True), ToOutput()]))

        # idx is the representation of the batch size which chosen to be as one sample (index) from the data.
        # ex: batch_features = [dataset.__getitem__(idx)[0] for idx in range(32)]
        # The batch_features is a list and len(batch_features)=32.
        fileh = tables.open_file("./enrollment.hdf5", mode="w")
        filters = tables.Filters(complevel=5, complib="blosc")
        train_label_list = []
        utterance_train = fileh.create_earray("/", "utterance_enrollment", tables.Atom.from_sctype(np.float32),
                                              shape=(0, 1, 80, 40),
                                              filters=filters)
        test_label_list = []
        utterance_test = fileh.create_earray("/", "utterance_evaluation", tables.Atom.from_sctype(np.float32),
                                             shape=(0, 1, 80, 40),
                                             filters=filters)
        # utterance_earray.append(feature_list)
        random.seed(123)
        for idx in range(len(dataset)):
            feature, label = dataset.__getitem__(idx)
            print(label, feature.shape)
            randint = random.randint(1, 10)
            if randint > 2:
                train_label_list.append(label)
                utterance_train.append(feature)
            else:
                test_label_list.append(label)
                utterance_test.append(feature)

        train_label_earray = fileh.create_earray("/", "label_enrollment", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                 filters=filters)
        train_label_earray.append(train_label_list)

        test_label_earray = fileh.create_earray("/", "label_evaluation", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                filters=filters)
        test_label_earray.append(test_label_list)

        # utterance_earray = fileh.create_earray("/", "utterance_train", tables.Atom.from_dtype(feature.dtype),shape=(0, feature.shape[1],feature.shape[2],feature.shape[3]), filters=filters)
        # utterance_earray.append(feature_list)
        # for x in range(feature.shape[0]):
        #    print(feature[x,].shape)
        #    utterance_earray.append(feature[x,])
        print(fileh)
        fileh.close()

    @staticmethod
    def save_enrollment_v2(file_path):
        dataset = AudioDataset(files_path=file_path, audio_dir="",  # args.audio_dir,
                               transform=Compose(
                                   [CMVN(), Feature_Cube(cube_shape=(1, 80, 40), augmentation=True), ToOutput()]))

        # idx is the representation of the batch size which chosen to be as one sample (index) from the data.
        # ex: batch_features = [dataset.__getitem__(idx)[0] for idx in range(32)]
        # The batch_features is a list and len(batch_features)=32.
        fileh = tables.open_file("./enrollment_v2.hdf5", mode="w")
        filters = tables.Filters(complevel=5, complib="blosc")
        train_label_list = []
        utterance_train = fileh.create_earray("/", "utterance_enrollment", tables.Atom.from_sctype(np.float32),
                                              shape=(0, 1, 80, 40),
                                              filters=filters)
        test_label_list = []
        utterance_test = fileh.create_earray("/", "utterance_evaluation", tables.Atom.from_sctype(np.float32),
                                             shape=(0, 1, 80, 40),
                                             filters=filters)
        # utterance_earray.append(feature_list)
        label_map = data_saver.get_label_map()
        random.seed(123)
        for idx in range(len(dataset)):
            feature, label = dataset.__getitem__(idx)
            label_index = label_map[label]
            print(label,label_index, feature.shape)
            randint = random.randint(1, 10)
            if randint > 2:
                train_label_list.append(label_index)
                utterance_train.append(feature)
            else:
                test_label_list.append(label_index)
                utterance_test.append(feature)

        train_label_earray = fileh.create_earray("/", "label_enrollment", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                 filters=filters)
        train_label_earray.append(train_label_list)

        test_label_earray = fileh.create_earray("/", "label_evaluation", tables.Atom.from_sctype(np.int16), shape=(0,),
                                                filters=filters)
        test_label_earray.append(test_label_list)

        # utterance_earray = fileh.create_earray("/", "utterance_train", tables.Atom.from_dtype(feature.dtype),shape=(0, feature.shape[1],feature.shape[2],feature.shape[3]), filters=filters)
        # utterance_earray.append(feature_list)
        # for x in range(feature.shape[0]):
        #    print(feature[x,].shape)
        #    utterance_earray.append(feature[x,])
        print(fileh)
        fileh.close()

if __name__ == '__main__':
    # add parser
    parser = argparse.ArgumentParser(description='Input pipeline')

    # The text file in which the paths to the audio files are available.
    # The path are relative to the directory of the audio files
    # Format of each line of the txt file is "class_label subject_dir/sound_file_name.ext"
    # Example of each line: 0 subject/sound.wav
    parser.add_argument('--file_path',
                        default=os.path.expanduser(
                            '~/github/3D-convolutional-speaker-recognition/code/0-input/file_path.txt'),
                        help='The file names for development phase')

    # The directory of the audio files separated by subject
    parser.add_argument('--audio_dir',
                        default=os.path.expanduser('~/github/3D-convolutional-speaker-recognition/code/0-input/Audio'),
                        help='Location of sound files')

    parser.add_argument('--task_type',
                        default="dev",
                        help='develpment or enrollment')
    args = parser.parse_args()

    if args.task_type == "development":
        data_saver.save_dev_v2(args.file_path)
    elif args.task_type == "enrollment":
        data_saver.save_enrollment_v2(args.file_path)

    '''
    dataset = AudioDataset(files_path=args.file_path, audio_dir="",#args.audio_dir,
                           transform=Compose([CMVN(), Feature_Cube(cube_shape=(20, 80, 40), augmentation=True), ToOutput()]))
   
    # idx is the representation of the batch size which chosen to be as one sample (index) from the data.
    # ex: batch_features = [dataset.__getitem__(idx)[0] for idx in range(32)] 
    # The batch_features is a list and len(batch_features)=32.
    fileh = tables.open_file("./outtest.hdf5", mode="w")
    filters = tables.Filters(complevel=5, complib="blosc")
    train_label_list = []
    utterance_train = fileh.create_earray("/", "utterance_train", tables.Atom.from_sctype(np.float32),
                                           shape=(0, 20, 80, 40),
                                           filters=filters)
    test_label_list = []
    utterance_test = fileh.create_earray("/", "utterance_test", tables.Atom.from_sctype(np.float32),
                                          shape=(0, 20, 80, 40),
                                          filters=filters)
    #utterance_earray.append(feature_list)
    random.seed(123)
    for idx in range(len(dataset)):
        feature, label = dataset.__getitem__(idx)
        print(label, feature.shape)
        randint = random.randint(1,10)
        if randint > 2:
            train_label_list.append(label)
            utterance_train.append(feature)
        else:
            test_label_list.append(label)
            utterance_test.append(feature)

    train_label_earray=fileh.create_earray("/","label_train",tables.Atom.from_sctype(np.int16),shape=(0,),filters=filters)
    train_label_earray.append(train_label_list)

    test_label_earray = fileh.create_earray("/", "label_test", tables.Atom.from_sctype(np.int16), shape=(0,),
                                             filters=filters)
    test_label_earray.append(test_label_list)

    #utterance_earray = fileh.create_earray("/", "utterance_train", tables.Atom.from_dtype(feature.dtype),shape=(0, feature.shape[1],feature.shape[2],feature.shape[3]), filters=filters)
    #utterance_earray.append(feature_list)
    #for x in range(feature.shape[0]):
    #    print(feature[x,].shape)
    #    utterance_earray.append(feature[x,])
    print(fileh)
    fileh.close()
    #print(feature.shape)
    #print(label)
    '''