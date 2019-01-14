#!/usr/bin/env python
# coding=utf-8
# wujian@17.9.19
"""
    Kaldi IO function implement(for binary format), test pass in Python 3.6.0
"""

import struct
import numpy as np

debug = False


def print_info(info):
    if debug:
        print(info)


def throw_on_error(ok, info=''):
    if not ok:
        raise RuntimeError(info)


def peek_char(fd):
    """ 
        Read a char and seek the point back
    """
    # peek_c = fd.read(1)
    # fd.seek(-1, 1)
    # see https://stackoverflow.com/questions/25070952/python-why-does-peek1-return-8k-bytes-instead-of-1-byte
    peek_c = fd.peek(1)[:1]
    if type(peek_c) == bytes:
        peek_c = bytes.decode(peek_c)
    return peek_c


def expect_space(fd):
    """ 
        Generally, there is a space following the string token, we need to consume it
    """
    space = fd.read(1)
    if type(space) == bytes:
        space = bytes.decode(space)
    throw_on_error(space == ' ', 'Expect space, but gets {}'.format(space))


def expect_binary(fd):
    """ 
        Read the binary flags in kaldi, the scripts only support reading egs in binary format
    """
    flags = fd.read(2)
    if type(flags) == bytes:
        flags = bytes.decode(flags)
    # throw_on_error(flags == '\0B', 'Expect binary flags \'B\', but gets {}'.format(flags))
    throw_on_error(flags == '\0B',
                   'Expect binary flags \'\\0B\', but gets {}'.format(flags))


def read_token(fd):
    """ 
        Read {token + ' '} from the file(this function also consume the space)
    """
    key = ''
    while True:
        c = fd.read(1)
        if type(c) == bytes:
            c = bytes.decode(c)
        if c == ' ' or c == '':
            break
        key += c
    return None if key == '' else key.strip()


def write_token(fd, token):
    """
        Write a string token, following a space symbol
    """
    if type(token) == str:
        token = str.encode(token)
    fd.write(token)
    fd.write(str.encode(' '))


def expect_token(fd, ref):
    """ 
        Check weather the token read equals to the reference
    """
    token = read_token(fd)
    throw_on_error(token == ref, 'Expect token \'{}\', but gets {}'.format(
        ref, token))


def read_key(fd):
    """ 
        Read the binary flags following the key(key might be None)
    """
    key = read_token(fd)
    if key:
        expect_binary(fd)
    return key


def write_binary_symbol(fd):
    """ 
        Write a binary symbol
    """
    fd.write(str.encode('\0B'))


def read_int32(fd):
    """ 
        Read a value in type 'int32' in kaldi setup
    """
    int_size = fd.read(1)
    if type(int_size) == bytes:
        int_size = bytes.decode(int_size)
    throw_on_error(int_size == '\04',
                   'Expect \'\\04\', but gets {}'.format(int_size))
    int_str = fd.read(4)
    int_val = struct.unpack('i', int_str)
    return int_val[0]


def write_int32(fd, int32):
    """
        Write a int32 number
    """
    fd.write(str.encode('\04'))
    int_pack = struct.pack('i', int32)
    fd.write(int_pack)


def read_float32(fd):
    """ 
        Read a value in type 'BaseFloat' in kaldi setup
    """
    float_size = fd.read(1)
    # throw_on_error(float_size == '\04')
    if type(float_size) == bytes:
        float_size = bytes.decode(float_size)
    throw_on_error(float_size == '\04',
                   'Expect \'\\04\', but gets {}'.format(float_size))
    float_str = fd.read(4)
    float_val = struct.unpack('f', float_str)
    return float_val


def read_common_mat(fd):
    """ 
        Read common matrix(for class Matrix in kaldi setup)
        see matrix/kaldi-matrix.cc::
            void Matrix<Real>::Read(std::istream & is, bool binary, bool add)
        Return a numpy ndarray object
    """
    mat_type = read_token(fd)
    print_info('\tType of the common matrix: {}'.format(mat_type))
    float_size = 4 if mat_type == 'FM' else 8
    float_type = np.float32 if mat_type == 'FM' else np.float64
    num_rows = read_int32(fd)
    num_cols = read_int32(fd)
    print_info('\tSize of the common matrix: {} x {}'.format(
        num_rows, num_cols))
    mat_data = fd.read(float_size * num_cols * num_rows)
    mat = np.fromstring(mat_data, dtype=float_type)
    return mat.reshape(num_rows, num_cols)


def write_common_mat(fd, mat):
    """
        Write a common matrix
    """
    assert mat.dtype == np.float32 or mat.dtype == np.float64
    mat_type = 'FM' if mat.dtype == np.float32 else 'DM'
    write_token(fd, mat_type)
    num_rows, num_cols = mat.shape
    write_int32(fd, num_rows)
    write_int32(fd, num_cols)
    fd.write(mat.tobytes())


def read_float_vec(fd):
    """
        Read float vector(for class Vector in kaldi setup)
        see matrix/kaldi-vector.cc
    """
    vec_type = read_token(fd)
    print_info('\tType of the common vector: {}'.format(vec_type))
    float_size = 4 if vec_type == 'FV' else 8
    float_type = np.float32 if vec_type == 'FV' else np.float64
    dim = read_int32(fd)
    print_info('\tDim of the common vector: {}'.format(dim))
    vec_data = fd.read(float_size * dim)
    return np.fromstring(vec_data, dtype=float_type)


def write_float_vec(fd, vec):
    """
        Write a float vector
    """
    assert vec.dtype == np.float32 or vec.dtype == np.float64
    vec_type = 'FV' if vec.dtype == np.float32 else 'DV'
    write_token(fd, vec_type)
    if vec.ndim != 1:
        raise RuntimeError("write_float_vec accept 1D-vector only")
    dim = vec.size
    write_int32(fd, dim)
    fd.write(vec.tobytes())


def read_int_vec(fd, direct_access=False):
    """
        Read int32 vector(alignments)
    """
    if direct_access:
        expect_binary(fd)
    vec_size = read_int32(fd)
    vec = np.zeros(vec_size, dtype=int)
    for i in range(vec_size):
        value = read_int32(fd)
        vec[i] = value
    return vec


def read_sparse_vec(fd):
    """ 
        Reference to function Read in SparseVector
        Return a list of key-value pair:
            [(I1, V1), ..., (In, Vn)]
    """
    expect_token(fd, 'SV')
    dim = read_int32(fd)
    num_elems = read_int32(fd)
    print_info('\tRead sparse vector(dim = {}, row = {})'.format(
        dim, num_elems))
    sparse_vec = []
    for _ in range(num_elems):
        index = read_int32(fd)
        value = read_float32(fd)
        sparse_vec.append((index, value))
    return sparse_vec


def read_sparse_mat(fd):
    """ 
        Reference to function Read in SparseMatrix
        A sparse matrix contains couples of sparse vector
    """
    mat_type = read_token(fd)
    print_info('\tFollowing matrix type: {}'.format(mat_type))
    num_rows = read_int32(fd)
    sparse_mat = []
    for _ in range(num_rows):
        sparse_mat.append(read_sparse_vec(fd))
    return sparse_mat


# TODO: optimize speed here, original IO 200x slower than uncompressed matrix
#       speed up 5x, now only 50x slower than uncompressed one
def uncompress(compress_data, cps_type, head):
    """ 
        In format CM(kOneByteWithColHeaders):
        PerColHeader, ...(x C), ... uint8 sequence ...
            first: get each PerColHeader pch for a single column
            then : using pch to uncompress each float in the column
        We load it seperately at a time 
        In format CM2(kTwoByte):
        ...uint16 sequence...
        In format CM3(kOneByte):
        ...uint8 sequence...
    """
    min_value, prange, num_rows, num_cols = head
    # mat = np.zeros([num_rows, num_cols])
    print_info('\tUncompress to matrix {} X {}'.format(num_rows, num_cols))
    if cps_type == 'CM':
        # checking compressed data size, 8 is the sizeof PerColHeader
        assert len(compress_data) == num_cols * (8 + num_rows)
        # type uint16
        phead_seq = struct.unpack('{}H'.format(4 * num_cols),
                                  compress_data[:8 * num_cols])
        phead_seq = np.array(phead_seq, dtype=np.float).reshape(num_cols, 4)
        # pchead: min_value + prange * 1.52590218966964e-05 * val
        pchead = np.transpose(phead_seq * 1.52590218966964e-05 * prange +
                              min_value)
        # type uint8
        uint8_seq = struct.unpack('{}B'.format(num_rows * num_cols),
                                  compress_data[8 * num_cols:])
        uint8_seq = np.array(
            uint8_seq, dtype=np.float).reshape(num_cols, num_rows)
        uint8_seq = np.transpose(uint8_seq)
        mat = np.zeros_like(uint8_seq)
        # precompute index
        le64_index = uint8_seq <= 64
        gt92_index = uint8_seq >= 193
        le92_index = np.logical_not(np.logical_xor(le64_index, gt92_index))
        # p[0] + (p[1] - p[0]) * c[le64_index] * (1 / 64.0)
        mat[le64_index] = (
            uint8_seq * (pchead[1] - pchead[0]) / 64.0 + pchead[0])[le64_index]
        # p[2] + (p[3] - p[2]) * (c[gt92_index] - 192) / 63.0
        mat[gt92_index] = ((uint8_seq - 192) * (pchead[3] - pchead[2]) / 63.0 +
                           pchead[2])[gt92_index]
        # p[1] + (p[2] - p[1]) * (c[le92_index] - 64) / 128.0
        mat[le92_index] = ((uint8_seq - 64) * (pchead[2] - pchead[1]) / 128.0 +
                           pchead[1])[le92_index]
        # for i in range(num_cols):
        #     # 1)    250x slower
        #     # pchead = uint16_to_floats(min_value, prange,
        #     #                           phead_seq[i * 4:i * 4 + 4])
        #     # for j in range(num_rows):
        #     #     mat[j, i] = uint8_to_float(uint8_seq[i, j], pchead)
        #     # 2)    70x slower
        #     uint8_seq[i] = uint8_to_float_vec(uint8_seq[i], le64_index[i],
        #                                       gt92_index[i], le92_index[i],
        #                                       pchead[i])
        # mat = np.transpose(uint8_seq)
    else:
        if cps_type == 'CM2':
            inc = float(prange / 65535.0)
            uint_seq = struct.unpack('{}H'.format(num_rows * num_cols),
                                     compress_data)
        else:
            inc = float(prange / 255.0)
            uint_seq = struct.unpack('{}B'.format(num_rows * num_cols),
                                     compress_data)
        uint_seq = np.array(
            uint_seq, dtype=np.float).reshape(num_rows, num_cols)
        mat = min_value + uint_seq * inc

    return mat


def read_index_tuple(fd):
    """ 
        Read the member in struct Index in nnet3/nnet-common.h  
        Return a tuple (n, t, x)
    """
    n = read_int32(fd)
    t = read_int32(fd)
    x = read_int32(fd)
    return (n, t, x)


def read_index(fd, index, cur_set):
    """ 
        Wapper to handle struct Index reading task(see: nnet3/nnet-common.cc)
            static void ReadIndexVectorElementBinary(std::istream &is, \
                int32 i, std::vector<Index> *vec)
        Return a tuple(n, t, x)
    """
    c = struct.unpack('b', fd.read(1))[0]
    if index == 0:
        if abs(c) < 125:
            return (0, c, 0)
        else:
            if c != 127:
                throw_on_error(
                    False,
                    'Unexpected character {} encountered while reading Index vector.'
                    .format(c))
            return read_index_tuple(fd)
    else:
        prev_index = cur_set[index - 1]
        if abs(c) < 125:
            return (prev_index[0], prev_index[1] + c, prev_index[2])
        else:
            if c != 127:
                throw_on_error(
                    False,
                    'Unexpected character {} encountered while reading Index vector.'
                    .format(c))
            return read_index_tuple(fd)


def read_index_vec(fd):
    """ 
        Read several Index and return as a list of index:
        [(n_1, t_1, x_1), ..., (n_m, t_m, x_m)]
    """
    expect_token(fd, '<I1V>')
    size = read_int32(fd)
    print_info('\tSize of index vector: {}'.format(size))
    index = []
    for i in range(size):
        cur_index = read_index(fd, i, index)
        index.append(cur_index)
    return index


def read_compress_mat(fd):
    """ 
        Reference to function Read in CompressMatrix
        Return a numpy ndarray object
    """
    cps_type = read_token(fd)
    print_info('\tFollowing matrix type: {}'.format(cps_type))
    head = struct.unpack('ffii', fd.read(16))
    print_info('\tCompress matrix header: {}'.format(head))
    # 8: sizeof PerColHeader
    # head: {min_value, range, num_rows, num_cols}
    num_rows, num_cols = head[2], head[3]
    if cps_type == 'CM':
        remain_size = num_cols * (8 + num_rows)
    elif cps_type == 'CM2':
        remain_size = 2 * num_rows * num_cols
    elif cps_type == 'CM3':
        remain_size = num_rows * num_cols
    else:
        throw_on_error(False,
                       'Unknown matrix compressing type: {}'.format(cps_type))
    # now uncompress it
    compress_data = fd.read(remain_size)
    mat = uncompress(compress_data, cps_type, head)
    return mat


def read_float_mat(fd, direct_access=False):
    """ 
        Reference to function Read in class GeneralMatrix
        Return compress_mat/sparse_mat/common_mat
    """
    if direct_access:
        expect_binary(fd)
    peek_mat_type = peek_char(fd)
    if peek_mat_type == 'C':
        return read_compress_mat(fd)
    elif peek_mat_type == 'S':
        return read_sparse_mat(fd)
    else:
        return read_common_mat(fd)


def read_nnet_io(fd):
    """ 
        Reference to function Read in class NnetIo
        each NnetIo contains three member: string, Index, GeneralMatrix
        I store them in the dict:{'name': ..., 'index': ..., 'matrix': ...}
    """
    expect_token(fd, '<NnetIo>')
    nnet_io = {}

    name = read_token(fd)
    nnet_io['name'] = name
    print_info('\tName of NnetIo: {}'.format(name))

    index = read_index_vec(fd)
    nnet_io['index'] = index
    print_info(index)

    mat = read_float_mat(fd)
    nnet_io['matrix'] = mat
    print_info(mat)
    expect_token(fd, '</NnetIo>')
    return nnet_io


def read_nnet3_egs(fd):
    """ 
        Reference to function Read in class NnetExample
        Return a list of dict, each dict represent a NnetIo object
        a NnetExample contains several NnetIo
    """
    expect_token(fd, '<Nnet3Eg>')
    expect_token(fd, '<NumIo>')
    # num of the NnetIo
    num_io = read_int32(fd)
    egs = []
    for _ in range(num_io):
        egs.append(read_nnet_io(fd))
    expect_token(fd, '</Nnet3Eg>')
    return egs


def read_nnet3_egs_ark(fd):
    """ 
        Usage:
        for key, eg in read_nnet3_egs(ark):
            print(key)
            ...
    """
    while True:
        key = read_key(fd)
        if not key:
            break
        egs = read_nnet3_egs(fd)
        yield key, egs


def read_ark(fd, matrix=True):
    """ 
        Usage:
        for key, mat in read_ark(ark):
            print(key)
            ...
    """
    loadf = read_float_mat if matrix else read_float_vec
    while True:
        key = read_key(fd)
        if not key:
            break
        obj = loadf(fd)
        yield key, obj


def read_ali(fd):
    while True:
        key = read_key(fd)
        if not key:
            break
        ali = read_int_vec(fd)
        yield key, ali


# -----------------test part-------------------
def _test_ali(ali_ark):
    with open(ali_ark, 'rb') as fd:
        for key, _ in read_ali(fd):
            print(key)


def _test_write_ark(src_ark, dst_ark):
    with open(src_ark, 'rb') as ark, open(dst_ark, 'wb') as dst:
        for key, mat in read_ark(ark):
            write_token(dst, key)
            write_binary_symbol(dst)  # in binary mode
            write_common_mat(dst, mat)


def _test_read_ark(src_ark):
    with open(src_ark, 'rb') as ark:
        for _, mat in read_ark(ark):
            print(mat.shape)


def _test_read_nnet3_egs_ark(egs_ark):
    with open(egs_ark, 'rb') as ark:
        for key, egs in read_nnet3_egs_ark(ark):
            print("{}: number of NnetIo: {:d}".format(key, len(egs)))


if __name__ == '__main__':
    # _test_write_ark("10.ark", "10.copy.ark")
    # _test_read_ark("10.copy.ark")
    # _test_ali()
    _test_read_nnet3_egs_ark("10.egs")
