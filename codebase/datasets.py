import numpy as np
import os
from scipy.io import loadmat
import scipy
import sys
import cPickle as pkl
import tensorbayes as tb
from itertools import izip
from utils import u2t, s2t

PATH = '/mnt/ilcompf5d0/user/rshu/data'

class Data(object):
    def __init__(self, images, labels=None, labeler=None, cast=False):
        """Data object constructs mini-batches to be fed during training

        images - (NHWC) data
        labels - (NK) one-hot data
        labeler - (tb.function) returns simplex value given an image
        cast - (bool) converts uint8 to [-1, 1] float
        """
        self.images = images
        self.labels = labels
        self.labeler = labeler
        self.cast = cast

    def preprocess(self, x):
        if self.cast:
            return u2t(x)
        else:
            return x

    def next_batch(self, bs):
        """Constructs a mini-batch of size bs without replacement
        """
        idx = np.random.choice(len(self.images), bs, replace=False)
        x = self.preprocess(self.images[idx])
        y = self.labeler(x) if self.labels is None else self.labels[idx]
        return x, y

class Mnist(object):
    def __init__(self, shape=(32, 32, 3)):
        """MNIST domain train/test data

        shape - (3,) HWC info
        """
        print "Loading MNIST"
        data = np.load(os.path.join(PATH, 'mnist.npz'))
        trainx = np.concatenate((data['x_train'], data['x_valid']), axis=0)
        trainy = np.concatenate((data['y_train'], data['y_valid']))
        trainy = np.eye(10)[trainy].astype('float32')

        testx = data['x_test']
        testy = data['y_test'].astype('int')
        testy = np.eye(10)[testy].astype('float32')

        trainx = self.resize_cast(trainx, shape)
        testx = self.resize_cast(testx, shape)

        self.train = Data(trainx, trainy)
        self.test = Data(testx, testy)

    @staticmethod
    def resize_cast(x, shape):
        H, W, C = shape
        x = x.reshape(-1, 28, 28)

        resized_x = np.empty((len(x), H, W), dtype='float32')
        for i, img in enumerate(x):
            # imresize returns uint8
            resized_x[i] = u2t(scipy.misc.imresize(img, (H, W)))

        # Retile to make RGB
        resized_x = resized_x.reshape(-1, H, W, 1)
        resized_x = np.tile(resized_x, (1, 1, 1, C))
        return resized_x


class Mnistm(object):
    def __init__(self, shape=(28, 28, 3), seed=0, npc=None):
        """Mnist-M domain train/test data

        shape - (3,) HWC info
        """
        print "Loading MNIST-M"
        data = pkl.load(open(os.path.join(PATH, 'mnistm_data.pkl')))
        labels = pkl.load(open(os.path.join(PATH, 'mnistm_labels.pkl')))

        trainx, trainy = data['train'], labels['train']
        validx, validy = data['valid'], labels['valid']
        testx, testy = data['test'], labels['test']
        trainx = np.concatenate((trainx, validx), axis=0)
        trainy = np.concatenate((trainy, validy), axis=0)

        trainx = self.resize_cast(trainx, shape)
        testx = self.resize_cast(testx, shape)

        self.train = Data(trainx, trainy)
        self.test = Data(testx, testy)

    @staticmethod
    def resize_cast(x, shape):
        H, W, C = shape
        x = x.reshape(-1, 28, 28, 3)

        resized_x = np.empty((len(x), H, W, 3), dtype='float32')
        for i, img in enumerate(x):
            # imresize returns uint8
            resized_x[i] = u2t(scipy.misc.imresize(img, (H, W)))

        return resized_x

class Svhn(object):
    def __init__(self, train='train'):
        """SVHN domain train/test data

        train - (str) flag for using 'train' or 'extra' data
        """
        print "Loading SVHN"
        train = loadmat(os.path.join(PATH, '{:s}_32x32.mat'.format(train)))
        test = loadmat(os.path.join(PATH, 'test_32x32.mat'))

        # Change format
        trainx, trainy = self.change_format(train)
        testx, testy = self.change_format(test)

        self.train = Data(trainx, trainy, cast=True)
        self.test = Data(testx, testy, cast=True)

    @staticmethod
    def change_format(mat):
        """Convert X: (HWCN) -> (NHWC) and Y: [1,...,10] -> one-hot
        """
        x = mat['X'].transpose((3, 0, 1, 2))
        y = mat['y'].reshape(-1)
        y[y == 10] = 0
        y = np.eye(10)[y]
        return x, y

class SynDigits(object):
    def __init__(self):
        """Synthetic SVHN domain train/test data
        """
        print "Loading SynDigits"
        train = loadmat(os.path.join(PATH, 'synth_train_32x32.mat'))
        test = loadmat(os.path.join(PATH, 'synth_test_32x32.mat'))

        # Change format
        trainx, trainy = self.change_format(train)
        testx, testy = self.change_format(test)

        self.train = Data(trainx, trainy, cast=True)
        self.test = Data(testx, testy, cast=True)

    @staticmethod
    def change_format(mat):
        """Convert X: (HWCN) -> (NHWC) and Y: [0,...,9] -> one-hot
        """
        x = mat['X'].transpose((3, 0, 1, 2))
        y = mat['y'].reshape(-1)
        y = np.eye(10)[y]
        return x, y

class Gtsrb(object):
    def __init__(self):
        """GTSRB street sign train/test adta
        """
        print "Loading GTSRB"
        data = loadmat(os.path.join(PATH, 'gtsrb.mat'))

        # Not really sure what happened here
        data['y'] = data['y'].reshape(-1)

        # Convert to one-hot
        n_class = data['y'].max() + 1
        data['y'] = np.eye(n_class)[data['y']]

        # Create train/test split
        with tb.nputils.FixedSeed(0):
            # Following Asymmetric Tri-training protocol
            # https://arxiv.org/pdf/1702.08400.pdf
            shuffle = np.random.permutation(len(data['X']))

        x = data['X'][shuffle]
        y = data['y'][shuffle]
        n = 31367
        trainx, trainy = x[:n], y[:n]
        testx, testy = x[n:], y[n:]

        self.train = Data(trainx, trainy, cast=True)
        self.test = Data(testx, testy, cast=True)

class SynSigns(object):
    def __init__(self):
        """Synthetic street signs domain train/test data
        """
        print "Loading SynSigns"
        data = loadmat(os.path.join(PATH, 'synsigns.mat'))

        # Not really sure what happened here
        data['y'] = data['y'].reshape(-1)

        # Convert to one-hot
        n_class = data['y'].max() + 1
        data['y'] = np.eye(n_class)[data['y']]

        # Create train/test split
        with tb.nputils.FixedSeed(0):
            shuffle = np.random.permutation(len(data['X']))

        x = data['X'][shuffle]
        y = data['y'][shuffle]
        n = 95000
        trainx, trainy = x[:n], y[:n]
        testx, testy = x[n:], y[n:]

        self.train = Data(trainx, trainy, cast=True)
        self.test = Data(testx, testy, cast=True)

class Cifar(object):
    def __init__(self):
        """CIFAR-10 modified domain train/test data

        Modification: one of the classes was removed to match STL
        """
        print "Loading CIFAR"
        train = loadmat(os.path.join(PATH, 'cifar_train.mat'))
        test = loadmat(os.path.join(PATH, 'cifar_test.mat'))

        # Get data
        trainx, trainy = train['X'], train['y']
        testx, testy = test['X'], test['y']

        # Convert to one-hot
        trainy = np.eye(9)[trainy.reshape(-1)]
        testy = np.eye(9)[testy.reshape(-1)]

        self.train = Data(trainx, trainy, cast=True)
        self.test = Data(testx, testy, cast=True)

class Stl(object):
    def __init__(self):
        """STL-10 modified domain train/test data

        Modification: one of the classes was removed to match CIFAR
        """
        print "Loading STL"
        sys.stdout.flush()
        PATH = '/mnt/ilcompf5d0/user/rshu/data'
        train = loadmat(os.path.join(PATH, 'stl_train.mat'))
        test = loadmat(os.path.join(PATH, 'stl_test.mat'))

        # Get data
        trainx, trainy = train['X'], train['y']
        testx, testy = test['X'], test['y']

        # Convert to one-hot
        trainy = np.eye(9)[trainy.reshape(-1)]
        testy = np.eye(9)[testy.reshape(-1)]

        self.train = Data(trainx, trainy, cast=True)
        self.test = Data(testx, testy, cast=True)

class PseudoData(object):
    def __init__(self, domain_id, domain, M):
        """Variable domain with psuedolabeler

        domain_id - (str) {Mnist,Mnistm,Svhn,etc}
        domain - (obj) {Mnist,Mnistm,Svhn,etc}
        M - (TensorDict) Model used for pseudolabeling
        """
        print "Constructing pseudodata"
        cast = 'mnist' not in domain_id
        print "{} uses casting: {}".format(domain_id, cast)
        labeler = tb.function(M.sess, [M.test_x], M.back_y)

        self.train = Data(domain.train.images, labeler=labeler, cast=cast)
        self.test = Data(domain.test.images, labeler=labeler, cast=cast)

def get_data(domain_id):
    """Returns Domain object based on domain_id
    """
    if domain_id == 'svhn':
        return datasets.Svhn()

    elif domain_id == 'digit':
        return datasets.SynDigits()

    elif domain_id == 'mnist32':
        return datasets.Mnist(shape=(32, 32, 3))

    elif domain_id == 'mnistm32':
        return datasets.Mnistm(shape=(32, 32, 3))

    elif domain_id == 'gtsrb':
        return datasets.Gtsrb()

    elif domain_id == 'sign':
        return datasets.SynSigns()

    elif domain_id == 'cifar':
        return datasets.Cifar()

    elif domain_id == 'stl':
        return datasets.Stl()

    else:
        raise Exception('dataset {:s} not recognized'.format(domain_id))
