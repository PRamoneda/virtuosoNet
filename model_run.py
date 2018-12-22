import torch
import torch.nn as nn
from torch.autograd import Variable
import pickle
import argparse
import math
import numpy as np
import asyncio
import shutil
import os
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import performanceWorm
import copy
import random
import xml_matching
import nnModel


parser = argparse.ArgumentParser()
parser.add_argument("-mode", "--sessMode", type=str, default='train', help="train or test")
# parser.add_argument("-model", "--nnModel", type=str, default="cnn", help="cnn or fcn")
parser.add_argument("-path", "--testPath", type=str, default="./test_pieces/mozart545-1/", help="folder path of test mat")
# parser.add_argument("-tset", "--trainingSet", type=str, default="dataOneHot", help="training set folder path")
parser.add_argument("-data", "--dataName", type=str, default="test", help="dat file name")
parser.add_argument("--resume", type=str, default="_best.pth.tar", help="best model path")
parser.add_argument("-tempo", "--startTempo", type=int, default=0, help="start tempo. zero to use xml first tempo")
parser.add_argument("-trill", "--trainTrill", type=bool, default=False, help="train trill")
parser.add_argument("--beatTempo", type=bool, default=True, help="cal tempo from beat level")
parser.add_argument("-voice", "--voiceNet", type=bool, default=True, help="network in voice level")
parser.add_argument("-vel", "--velocity", type=str, default='50,65', help="mean velocity of piano and forte")
parser.add_argument("-dev", "--device", type=int, default=0, help="cuda device number")
parser.add_argument("-code", "--modelCode", type=str, default='ggnn_non_ar_test', help="code name for saving the model")
parser.add_argument("-comp", "--composer", type=str, default='Chopin', help="composer name of the input piece")
parser.add_argument("--latent", type=float, default=0, help='initial_z value')
parser.add_argument("-bp", "--boolPedal", type=bool, default=False, help='initial_z value')
parser.add_argument("-loss", "--trainingLoss", type=str, default='CE', help='type of training loss')


args = parser.parse_args()


class NetParams:
    class Param:
        def __init__(self):
            self.size = 0
            self.layer = 0
            self.input = 0

    def __init__(self):
        self.note = self.Param()
        self.onset = self.Param()
        self.beat = self.Param()
        self.measure = self.Param()
        self.final = self.Param()
        self.voice = self.Param()
        self.sum = self.Param()
        self.encoder = self.Param()
        self.input_size = 0
        self.output_size = 0

### parameters


learning_rate = 0.0003
TIME_STEPS = 500
VALID_STEPS = 3000
print('Learning Rate and Time Steps are ', learning_rate, TIME_STEPS)
num_epochs = 150
num_key_augmentation = 1

SCORE_INPUT = 80 #score information only
DROP_OUT = 0.25
TOTAL_OUTPUT = 16


num_prime_param = 11
num_second_param = 0
num_trill_param = 5
num_voice_feed_param = 0 # velocity, onset deviation
num_tempo_info = 0
num_dynamic_info = 0 # distance from marking, dynamics vector 4, mean_piano, forte marking and velocity = 4
is_trill_index_score = -11
is_trill_index_concated = -11 - (num_prime_param + num_second_param)


QPM_INDEX = 0
# VOICE_IDX = 11
TEMPO_IDX = 29
PITCH_IDX = 16
QPM_PRIMO_IDX = 5
TEMPO_PRIMO_IDX = -2
GRAPH_KEYS = ['onset', 'forward', 'melisma', 'rest', 'voice', 'boundary', 'slur']
N_EDGE_TYPE = len(GRAPH_KEYS) * 2
# mean_vel_start_index = 7
# vel_vec_start_index = 33

batch_size = 1

torch.cuda.set_device(args.device)
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

NET_PARAM = NetParams()
NET_PARAM.input_size = SCORE_INPUT
NET_PARAM.output_size = num_prime_param

if 'ggnn_non_ar' in args.modelCode:

    NET_PARAM.note.layer = 2
    NET_PARAM.note.size = 64
    NET_PARAM.beat.layer = 2
    NET_PARAM.beat.size = 32
    NET_PARAM.measure.layer = 1
    NET_PARAM.measure.size = 16
    NET_PARAM.final.layer = 1
    NET_PARAM.final.size = 24

    NET_PARAM.encoder.size = 64
    NET_PARAM.encoder.layer = 2

    NET_PARAM.final.input = (NET_PARAM.note.size + NET_PARAM.beat.size +
                             NET_PARAM.measure.size) * 2 + NET_PARAM.encoder.size + \
                            num_tempo_info + num_dynamic_info
    NET_PARAM.encoder.input = (NET_PARAM.note.size + NET_PARAM.beat.size +
                               NET_PARAM.measure.size + NET_PARAM.voice.size) * 2 \
                              + num_prime_param
    MODEL = nnModel.GGNN_HAN(NET_PARAM, DEVICE).to(DEVICE)

elif 'ggnn_ar' in args.modelCode:

    NET_PARAM.note.layer = 2
    NET_PARAM.note.size = 64
    NET_PARAM.beat.layer = 2
    NET_PARAM.beat.size = 64
    NET_PARAM.measure.layer = 1
    NET_PARAM.measure.size = 64
    NET_PARAM.final.layer = 1
    NET_PARAM.final.size = 64

    NET_PARAM.encoder.size = 64
    NET_PARAM.encoder.layer = 2

    NET_PARAM.final.input = (NET_PARAM.note.size + NET_PARAM.beat.size +
                             NET_PARAM.measure.size) * 2 + NET_PARAM.encoder.size + \
                            num_tempo_info + num_dynamic_info
    NET_PARAM.encoder.input = (NET_PARAM.note.size + NET_PARAM.beat.size +
                               NET_PARAM.measure.size + NET_PARAM.voice.size) * 2 \
                              + num_prime_param
    MODEL = nnModel.GGNN_HAN(NET_PARAM, DEVICE).to(DEVICE)

elif 'vae' in args.modelCode:
    NET_PARAM.note.layer = 2
    NET_PARAM.note.size = 64
    NET_PARAM.beat.layer = 2
    NET_PARAM.beat.size = 32
    NET_PARAM.measure.layer = 1
    NET_PARAM.measure.size = 16
    NET_PARAM.final.layer = 1
    NET_PARAM.final.size = 64
    NET_PARAM.voice.layer = 2
    NET_PARAM.voice.size = 64
    NET_PARAM.sum.layer = 2
    NET_PARAM.sum.size = 64

    NET_PARAM.encoder.size = 64
    NET_PARAM.encoder.layer = 2

    NET_PARAM.final.input = (NET_PARAM.note.size + NET_PARAM.voice.size + NET_PARAM.beat.size +
                             NET_PARAM.measure.size) * 2 + NET_PARAM.encoder.size + \
                            num_tempo_info + num_dynamic_info
    NET_PARAM.encoder.input = (NET_PARAM.note.size + NET_PARAM.beat.size +
                               NET_PARAM.measure.size + NET_PARAM.voice.size) * 2 \
                              + num_prime_param
    MODEL = nnModel.HAN_VAE(NET_PARAM, DEVICE).to(DEVICE)
elif 'han' in args.modelCode:
    NET_PARAM.note.layer = 4
    NET_PARAM.note.size = 64
    NET_PARAM.beat.layer = 2
    NET_PARAM.beat.size = 32
    NET_PARAM.measure.layer = 1
    NET_PARAM.measure.size = 16
    NET_PARAM.final.layer = 1
    NET_PARAM.final.size = 64
    NET_PARAM.voice.layer = 2
    NET_PARAM.voice.size = 64

    num_voice_feed_param = 2  # velocity, onset deviation
    num_tempo_info = 3
    num_dynamic_info = 4
    NET_PARAM.final.input = NET_PARAM.note.size * 2 + NET_PARAM.beat.size * 2 + \
                            NET_PARAM.measure.size * 2 + NET_PARAM.output_size + num_tempo_info + num_voice_feed_param + num_dynamic_info
    NET_PARAM.encoder.input = (NET_PARAM.note.size + NET_PARAM.beat.size +
                               NET_PARAM.measure.size + NET_PARAM.voice.size) * 2 \
                              + num_prime_param
    MODEL = nnModel.HAN(NET_PARAM, DEVICE).to(DEVICE)
else:
    print('Unclassified model code')


Second_NET_PARAM = copy.deepcopy(NET_PARAM)
Second_NET_PARAM.input_size = SCORE_INPUT + NET_PARAM.output_size
Second_NET_PARAM.output_size = num_second_param
Second_NET_PARAM.final.input += Second_NET_PARAM.output_size - NET_PARAM.output_size - num_tempo_info - num_voice_feed_param - num_dynamic_info

TrillNET_Param = copy.deepcopy(NET_PARAM)
TrillNET_Param.input_size = SCORE_INPUT + NET_PARAM.output_size + Second_NET_PARAM.output_size
TrillNET_Param.output_size = num_trill_param
TrillNET_Param.note.size = (NET_PARAM.note.size + NET_PARAM.beat.size + NET_PARAM.measure.size + NET_PARAM.voice.size) * 2 + NET_PARAM.output_size + Second_NET_PARAM.output_size
TrillNET_Param.note.layer = 3

### Model

# class PerformanceEncoder(GGNN_HAN):
#     def __init__(self, network_parameters):
#         super(perfor)

def vae_loss(recon_x, x, mu, logvar):
    MSE = nn.MSELoss(recon_x, x.view(-1, 784), reduction='sum')

    # see Appendix B from VAE paper:
    # Kingma and Welling. Auto-Encoding Variational Bayes. ICLR, 2014
    # https://arxiv.org/abs/1312.6114
    # 0.5 * sum(1 + log(sigma^2) - mu^2 - sigma^2)
    KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    return MSE + KLD


# model = BiRNN(input_size, hidden_size, num_layers, num_output).to(device)
# second_model = ExtraHAN(NET_PARAM).to(device)
trill_model =nnModel.TrillRNN(TrillNET_Param, is_trill_index_concated).to(DEVICE)


criterion = nn.MSELoss()
optimizer = torch.optim.Adam(MODEL.parameters(), lr=learning_rate)
# second_optimizer = torch.optim.Adam(second_model.parameters(), lr=learning_rate)
trill_optimizer = torch.optim.Adam(trill_model.parameters(), lr=learning_rate)


def save_checkpoint(state, is_best, filename=args.modelCode, model_name='prime'):
    save_name = model_name + '_' + filename + '_checkpoint.pth.tar'
    torch.save(state, save_name)
    if is_best:
        best_name = model_name + '_' + filename + '_best.pth.tar'
        shutil.copyfile(save_name, best_name)


def key_augmentation(data_x, key_change):
    # key_change = 0
    if key_change == 0:
        return data_x
    data_x_aug = copy.deepcopy(data_x)
    pitch_start_index = PITCH_IDX
    # while key_change == 0:
    #     key_change = random.randrange(-5, 7)
    for data in data_x_aug:
        octave = data[pitch_start_index]
        pitch_class_vec = data[pitch_start_index+1:pitch_start_index+13]
        pitch_class = pitch_class_vec.index(1)
        new_pitch = pitch_class + key_change
        if new_pitch < 0:
            octave -= 0.25
        elif new_pitch > 12:
            octave += 0.25
        new_pitch = new_pitch % 12

        new_pitch_vec = [0] * 13
        new_pitch_vec[0] = octave
        new_pitch_vec[new_pitch+1] = 1

        data[pitch_start_index: pitch_start_index+13] = new_pitch_vec

    return data_x_aug

def edges_to_matrix(edges, num_notes):
    num_keywords = len(GRAPH_KEYS)
    matrix = np.zeros((N_EDGE_TYPE, num_notes, num_notes))

    for edg in edges:
        if edg[2] not in GRAPH_KEYS:
            continue
        edge_type = GRAPH_KEYS.index(edg[2])
        matrix[edge_type, edg[0], edg[1]] = 1
        if edge_type != 0:
            matrix[edge_type+num_keywords, edg[1], edg[0]] = 1
        else:
            matrix[edge_type, edg[1], edg[0]] = 1

    matrix[num_keywords, :,:] = np.identity(num_notes)

    # for k in range(num_keywords):
    #     selected_key = GRAPH_KEYS[k]
    #     selected_edge = edges[selected_key]
    #     for i in range(time_steps):
    #         abs_index = start_index + i
    #         for edge_index in selected_edge[abs_index]:
    #             if 0 <= edge_index - start_index < time_steps:
    #                 matrix[k, i, edge_index-start_index] = 1

    matrix = torch.Tensor(matrix)
    return matrix


def edges_to_sparse_tensor(edges):
    num_keywords = len(GRAPH_KEYS)
    edge_list = []
    edge_type_list = []

    for edg in edges:
        edge_type = GRAPH_KEYS.index(edg[2])
        edge_list.append(edg[0:2])
        edge_list.append([edg[1], edg[0]])
        edge_type_list.append(edge_type)
        if edge_type != 0:
            edge_type_list.append(edge_type+num_keywords)
        else:
            edge_type_list.append(edge_type)

        edge_list = torch.LongTensor(edge_list)
    edge_type_list = torch.FloatTensor(edge_type_list)

    matrix = torch.sparse.FloatTensor(edge_list.t(), edge_type_list)

    return matrix


def categorize_value_to_vector(y, bins):
    vec_length = sum([len(x) for x in bins])
    for note in y:
        total_vec = []
        for i in range(TOTAL_OUTPUT):
            temp_vec = [0] * (len(bins[i]) -1)
            temp_vec[int(note[i])] = 1
            total_vec += temp_vec
        note = total_vec

    return y


def perform_xml(input, input_y, edges, note_locations, tempo_stats, valid_y = None, initial_z=False):
    num_notes = input.shape[1]
    total_valid_batch = int(math.ceil(num_notes / VALID_STEPS))
    with torch.no_grad():  # no need to track history in validation
        model_eval = MODEL.eval()
        trill_model_eval = trill_model.eval()

        total_output = []
        if num_notes < VALID_STEPS:
            if input_y.shape[1] > 1:
                prime_input_y = input_y[:, :, 0:num_prime_param].view(1, -1, num_prime_param)
            else:
                prime_input_y = input_y[:, :, 0:num_prime_param].view(1, 1, num_prime_param)
            batch_graph = edges.to(DEVICE)
            prime_outputs, _, _, note_hidden_out = model_eval(input, prime_input_y, batch_graph,
                                                              note_locations=note_locations, start_index=0,
                                                              step_by_step=False, initial_z=initial_z)
            # second_inputs = torch.cat((input,prime_outputs), 2)
            # second_input_y = input_y[:,:,num_prime_param:num_prime_param+num_second_param].view(1,-1,num_second_param)
            # model_eval = second_model.eval()
            # second_outputs = model_eval(second_inputs, second_input_y, note_locations, 0, step_by_step=True)
            if torch.sum(input[:, :, is_trill_index_score]) > 0:
                trill_inputs = torch.cat((input, prime_outputs), 2)
                notes_hidden_cat = torch.cat((note_hidden_out, prime_outputs), 2)
                trill_outputs = trill_model_eval(trill_inputs, notes_hidden_cat)
            else:
                trill_outputs = torch.zeros(1, num_notes, num_trill_param).to(DEVICE)

            outputs = torch.cat((prime_outputs, trill_outputs), 2)
        else:
            for i in range(total_valid_batch):
                batch_start = i * VALID_STEPS
                if i == total_valid_batch-1:
                    batch_end = num_notes
                else:
                    batch_end = (i+1) * VALID_STEPS
                if input_y.shape[1] > 1:
                    prime_input_y = input_y[:,batch_start:batch_end,0:num_prime_param].view(1,-1,num_prime_param)
                else:
                    prime_input_y = input_y[:, :, 0:num_prime_param].view(1, 1, num_prime_param)
                batch_input = input[:,batch_start:batch_end,:]
                batch_graph = edges[:,batch_start:batch_end, batch_start:batch_end].to(DEVICE)
                prime_outputs, _, _, note_hidden_out = model_eval(batch_input, prime_input_y, batch_graph, note_locations=note_locations, start_index=0, step_by_step=False, initial_z=initial_z)
                # second_inputs = torch.cat((input,prime_outputs), 2)
                # second_input_y = input_y[:,:,num_prime_param:num_prime_param+num_second_param].view(1,-1,num_second_param)
                # model_eval = second_model.eval()
                # second_outputs = model_eval(second_inputs, second_input_y, note_locations, 0, step_by_step=True)
                if torch.sum(input[:,batch_start:batch_end,is_trill_index_score])> 0:
                    trill_inputs = torch.cat((batch_input, prime_outputs), 2)
                    notes_hidden_cat = torch.cat((note_hidden_out,prime_outputs), 2)
                    trill_outputs = trill_model_eval(trill_inputs, notes_hidden_cat)
                else:
                    trill_outputs = torch.zeros(1, batch_end-batch_start, num_trill_param).to(DEVICE)

                temp_outputs = torch.cat((prime_outputs, trill_outputs),2)
                total_output.append(temp_outputs)
            outputs = torch.cat(total_output, 1)
        return outputs


def batch_time_step_run(x, y, prev_feature, edges, note_locations, align_matched, step, batch_size=batch_size, time_steps=TIME_STEPS, model=MODEL, trill_model=trill_model):
    num_total_notes = len(x)
    if step < total_batch_num - 1:
        batch_start = step * batch_size * time_steps
        batch_end = (step + 1) * batch_size * time_steps
        batch_x = torch.Tensor(x[batch_start:batch_end])
        batch_y = torch.Tensor(y[batch_start:batch_end])
        align_matched = torch.Tensor(align_matched[batch_start:batch_end])
        # input_y = torch.Tensor(prev_feature[batch_start:batch_end])
        # input_y = torch.cat((zero_tensor, batch_y[0:batch_size * time_steps-1]), 0).view((batch_size, time_steps,num_output)).to(device)
    elif num_total_notes < time_steps:
        batch_x = torch.Tensor(x)
        batch_y = torch.Tensor(y)
        align_matched = torch.Tensor(align_matched)
        batch_start = 0
    else:
        # num_left_data = data_size % batch_size*time_steps
        batch_start = num_total_notes-(batch_size * time_steps)
        batch_x = torch.Tensor(x[batch_start:])
        batch_y = torch.Tensor(y[batch_start:])
        align_matched = torch.Tensor(align_matched[batch_start:])
        # input_y = torch.Tensor(prev_feature[batch_start:])
        # input_y = torch.cat((zero_tensor, batch_y[0:batch_size * time_steps-1]), 0).view((batch_size, time_steps,num_output)).to(device)
    batch_x = batch_x.view((batch_size, -1, SCORE_INPUT)).to(DEVICE)
    batch_y = batch_y.view((batch_size, -1, TOTAL_OUTPUT)).to(DEVICE)
    align_matched = align_matched.view((batch_size, -1, 1)).to(DEVICE)
    # input_y = input_y.view((batch_size, time_steps, TOTAL_OUTPUT)).to(device)

    # async def train_prime(batch_x, batch_y, input_y, model):
    prime_batch_x = batch_x
    prime_batch_y = batch_y[:,:,0:num_prime_param]
    prime_batch_y *= align_matched


    batch_graph = edges[:,batch_start:batch_start+time_steps, batch_start:batch_start+time_steps].to(DEVICE)

    model_train = model.train()
    prime_outputs, perform_mu, perform_var, note_out \
        = model_train(prime_batch_x, prime_batch_y, batch_graph, note_locations, batch_start, step_by_step=False)
    prime_outputs *= align_matched

    tempo_loss = cal_tempo_loss_in_beat(prime_outputs, prime_batch_y, note_locations, batch_start)
    mse_loss = criterion(prime_outputs[:,:,1:], prime_batch_y[:,:,1:])
    perform_kld = -0.5 * torch.sum(1 + perform_var - perform_mu.pow(2) - perform_var.exp())
    prime_loss = tempo_loss + mse_loss + perform_kld
    optimizer.zero_grad()
    prime_loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 0.25)
    optimizer.step()

    if torch.sum(batch_x[:,:,is_trill_index_score]) > 0:
        trill_batch_x = torch.cat((batch_x, batch_y[:,:,0:num_prime_param+num_second_param]), 2)
        note_out_cat = torch.cat((note_out, batch_y[:,:,0:num_prime_param+num_second_param]),2)
        trill_batch_y = batch_y[:,:,-num_trill_param:]
        model_train = trill_model.train()
        trill_output = model_train(trill_batch_x, note_out_cat)
        trill_loss = criterion(trill_output, trill_batch_y)
        trill_optimizer.zero_grad()
        trill_loss.backward()
        torch.nn.utils.clip_grad_norm_(trill_model.parameters(), 0.25)
        trill_optimizer.step()
    else:
        trill_loss = torch.zeros(1)

    # loss = criterion(outputs, batch_y)
    # tempo_loss = criterion(prime_outputs[:, :, 0], prime_batch_y[:, :, 0])
    vel_loss = criterion(prime_outputs[:, :, 1], prime_batch_y[:, :, 1])
    dev_loss = criterion(prime_outputs[:, :, 2], prime_batch_y[:, :, 2])
    return tempo_loss, vel_loss, dev_loss, trill_loss, perform_kld

def cal_tempo_loss_in_beat(pred_x, true_x, note_locations, start_index):
    previous_beat = -1
    num_notes = pred_x.shape[1]
    start_beat = note_locations[start_index].beat
    num_beats = note_locations[num_notes+start_index-1].beat - start_beat + 1


    pred_beat_tempo = torch.zeros([num_beats]).to(DEVICE)
    true_beat_tempo = torch.zeros([num_beats]).to(DEVICE)
    for i in range(num_notes):
        current_beat = note_locations[i+start_index].beat
        if current_beat > previous_beat:
            previous_beat = current_beat
            pred_beat_tempo[current_beat-start_beat] = pred_x[0,i,QPM_INDEX]
            true_beat_tempo[current_beat-start_beat] = true_x[0,i,QPM_INDEX]

    tempo_loss = criterion(pred_beat_tempo, true_beat_tempo)
    return tempo_loss


### training

if args.sessMode == 'train':
    model_parameters = filter(lambda p: p.requires_grad, MODEL.parameters())
    params = sum([np.prod(p.size()) for p in model_parameters])
    print('Number of Network Parameters is ', params)


    # load data
    print('Loading the training data...')
    with open(args.dataName + ".dat", "rb") as f:
        u = pickle._Unpickler(f)
        u.encoding = 'latin1'
        # p = u.load()
        # complete_xy = pickle.load(f)
        complete_xy = u.load()

    with open(args.dataName + "_stat.dat", "rb") as f:
        u = pickle._Unpickler(f)
        u.encoding = 'latin1'
        if args.trainingLoss == 'CE':
            means, stds, bins = u.load()
        else:
            means, stds = u.load()

    # perform_num = len(complete_xy)
    if args.trainingLoss == 'MSE':
        tempo_stats = [means[1][0], stds[1][0]]
    else:
        tempo_stats = [0,0]

    # train_perf_num = int(perform_num * training_ratio)
    train_xy = complete_xy['train']
    test_xy = complete_xy['valid']
    print('number of train performances: ', len(train_xy), 'number of valid perf: ', len(test_xy))

    print(train_xy[0][0][0])
    best_prime_loss = float("inf")
    best_second_loss = float("inf")
    best_trill_loss = float("inf")
    # total_step = len(train_loader)
    for epoch in range(num_epochs):
        tempo_loss_total =[]
        vel_loss_total =[]
        second_loss_total =[]
        trill_loss_total =[]
        kld_total = []
        for xy_tuple in train_xy:
            train_x = xy_tuple[0]
            train_y = xy_tuple[1]
            if args.trainingLoss == 'CE':
                train_y = categorize_value_to_vector(train_y, bins)
            prev_feature = xy_tuple[2]
            note_locations = xy_tuple[3]
            align_matched = xy_tuple[4]
            edges = xy_tuple[5]

            data_size = len(train_x)
            graphs = edges_to_matrix(edges, data_size)
            # graphs = edges_to_sparse_tensor(edges)
            total_batch_num = int(math.ceil(data_size / (TIME_STEPS * batch_size)))

            key_lists = [0]
            key = 0
            for i in range(num_key_augmentation):
                while key in key_lists:
                    key = random.randrange(-5, 7)
                key_lists.append(key)

            for i in range(num_key_augmentation+1):
                key = key_lists[i]
                temp_train_x = key_augmentation(train_x, key)

                for step in range(total_batch_num):
                    tempo_loss, vel_loss, second_loss, trill_loss, kld = \
                        batch_time_step_run(temp_train_x, train_y, prev_feature, graphs, note_locations, align_matched, step)
                    # optimizer.zero_grad()
                    # loss.backward()
                    # optimizer.step()
                    # print(tempo_loss)
                    tempo_loss_total.append(tempo_loss.item())
                    vel_loss_total.append(vel_loss.item())
                    second_loss_total.append(second_loss.item())
                    trill_loss_total.append(trill_loss.item())
                    kld_total.append(kld.item())

        print('Epoch [{}/{}], Loss - Tempo: {:.4f}, Vel: {:.4f}, Deviation: {:.4f}, Trill: {:.4f}, KLD: {:.4f}'
              .format(epoch + 1, num_epochs, np.mean(tempo_loss_total), np.mean(vel_loss_total),
                      np.mean(second_loss_total), np.mean(trill_loss_total), np.mean(kld_total) *1000))


        ## Validation
        valid_loss_total = []
        tempo_loss_total =[]
        vel_loss_total =[]
        second_loss_total =[]
        trill_loss_total =[]
        for xy_tuple in test_xy:
            test_x = xy_tuple[0]
            test_y = xy_tuple[1]
            prev_feature = xy_tuple[2]
            note_locations = xy_tuple[3]
            align_matched = xy_tuple[4]
            edges = xy_tuple[5]
            graphs = edges_to_matrix(edges, len(test_x))


            batch_x = torch.Tensor(test_x).view((1, -1, SCORE_INPUT)).to(DEVICE)
            batch_y = torch.Tensor(test_y).view((1, -1, TOTAL_OUTPUT)).to(DEVICE)
            input_y = torch.Tensor(prev_feature).view((1, -1, TOTAL_OUTPUT)).to(DEVICE)
            align_matched = torch.Tensor(align_matched).view(1, -1, 1).to(DEVICE)
            align_matched = align_matched.repeat(1,1,TOTAL_OUTPUT)
            # if args.trainTrill:
            #     input_y = torch.Tensor(prev_feature).view((1, -1, output_size)).to(device)
            # else:
            #     input_y = torch.Tensor(prev_feature)
            #     input_y = input_y[:,:-num_trill_param].view((1, -1, output_size - num_trill_param)).to(device)
            # hidden = model.init_hidden(1)
            # final_hidden = model.init_final_layer(1)
            # outputs, hidden, final_hidden = model(batch_x, input_y, hidden, final_hidden)

            # batch_x = Variable(torch.Tensor(test_x)).view((1, -1, SCORE_INPUT)).to(device)
            #
            outputs = perform_xml(batch_x, input_y, graphs, note_locations, tempo_stats, valid_y=batch_y)

            outputs *= align_matched
            batch_y *= align_matched
            # outputs = outputs.view(1,-1,NET_PARAM.output_size)
            # outputs = torch.Tensor(outputs).view((1, -1, output_size)).to(device)
            # if args.trainTrill:
            #     outputs = torch.Tensor(outputs).view((1, -1, output_size))
            # else:
            #     outputs = torch.Tensor(outputs).view((1, -1, output_size - num_trill_param))
            valid_loss = criterion(outputs[:,:,1:-num_trill_param], batch_y[:,:,1:-num_trill_param])
            tempo_loss = cal_tempo_loss_in_beat(outputs, batch_y, note_locations, 0)
            vel_loss = criterion(outputs[:,:,1], batch_y[:,:,1])
            second_loss = criterion(outputs[:,:,2],
                                    batch_y[:,:,2])
            trill_loss = criterion(outputs[:,:,-num_trill_param:], batch_y[:,:,-num_trill_param:])

            valid_loss_total.append(valid_loss.item())
            tempo_loss_total.append(tempo_loss.item())
            vel_loss_total.append(vel_loss.item())
            second_loss_total.append(second_loss.item())
            trill_loss_total.append(trill_loss.item())

        mean_valid_loss = np.mean(valid_loss_total)
        mean_tempo_loss = np.mean(tempo_loss_total)
        mean_valid_loss = (mean_valid_loss + mean_tempo_loss * 0.5) / 1.5
        mean_vel_loss =  np.mean(vel_loss_total)
        mean_second_loss = np.mean(second_loss_total)
        mean_trill_loss = np.mean(trill_loss_total)
        print("Valid Loss= {:.4f} , Tempo: {:.4f}, Vel: {:.4f}, Deviation: {:.4f}, Trill: {:.4f}"
              .format(mean_valid_loss, mean_tempo_loss , mean_vel_loss,
                      mean_second_loss, mean_trill_loss))

        mean_prime_loss = (mean_tempo_loss + mean_vel_loss + mean_second_loss) /3
        is_best = mean_valid_loss < best_prime_loss
        best_prime_loss = min(mean_valid_loss, best_prime_loss)


        is_best_trill = mean_trill_loss < best_trill_loss
        best_trill_loss = min(mean_trill_loss, best_trill_loss)


        save_checkpoint({
            'epoch': epoch + 1,
            'state_dict': MODEL.state_dict(),
            'best_valid_loss': best_prime_loss,
            'optimizer': optimizer.state_dict(),
        }, is_best, model_name='prime')
        save_checkpoint({
            'epoch': epoch + 1,
            'state_dict': trill_model.state_dict(),
            'best_valid_loss': best_trill_loss,
            'optimizer': trill_optimizer.state_dict(),
        }, is_best_trill, model_name='trill')


    #end of epoch



elif args.sessMode=='test':
### test session
    with open(args.dataName + "_stat.dat", "rb") as f:
        u = pickle._Unpickler(f)
        u.encoding = 'latin1'
        means, stds = u.load()
    if os.path.isfile('prime_' + args.modelCode + args.resume):
        print("=> loading checkpoint '{}'".format(args.modelCode + args.resume))
        model_codes = ['prime', 'trill']
        for i in range(2):
            filename = model_codes[i] + '_' + args.modelCode + args.resume
            checkpoint = torch.load(filename)
            # args.start_epoch = checkpoint['epoch']
            # best_valid_loss = checkpoint['best_valid_loss']
            if i == 0:
                MODEL.load_state_dict(checkpoint['state_dict'])
            elif i==1:
                trill_model.load_state_dict(checkpoint['state_dict'])
            # optimizer.load_state_dict(checkpoint['optimizer'])
            print("=> loaded checkpoint '{}' (epoch {})"
                  .format(filename, checkpoint['epoch']))
    else:
        print("=> no checkpoint found at '{}'".format(args.resume))
    path_name = args.testPath
    composer_name = args.composer
    vel_pair = (int(args.velocity.split(',')[0]), int(args.velocity.split(',')[1]))
    test_x, xml_notes, xml_doc, edges, note_locations = xml_matching.read_xml_to_array(path_name, means, stds, args.startTempo, composer_name, vel_pair)
    batch_x = torch.Tensor(test_x).to(DEVICE)
    batch_x = batch_x.view(1, -1, SCORE_INPUT)

    for i in range(len(stds)):
        for j in range(len(stds[i])):
            if stds[i][j] < 1e-4:
                stds[i][j] = 1
    #
    # test_x = np.asarray(test_x)
    # timestep_quantize_num = int(math.ceil(test_x.shape[0] / time_steps))
    # padding_size = timestep_quantize_num * time_steps - test_x.shape[0]
    # test_x_padded = np.pad(test_x, ((0, padding_size), (0, 0)), 'constant')
    # batch_x = test_x_padded.reshape((-1, time_steps, input_size))
    # batch_x = Variable(torch.from_numpy(batch_x)).float().to(device)
    # tempos = xml_doc.get_tempos()

    if args.startTempo == 0:
        start_tempo = xml_notes[0].state_fixed.qpm / 60 * xml_notes[0].state_fixed.divisions
        start_tempo = math.log(start_tempo, 10)
        # start_tempo_norm = (start_tempo - means[1][0]) / stds[1][0]
    else:
        start_tempo = math.log(args.startTempo, 10)
    start_tempo_norm = (start_tempo - means[1][0]) / stds[1][0]
    input_y = torch.zeros(1, 1, TOTAL_OUTPUT)
    # if args.trainTrill:
    #     input_y = torch.zeros(1, 1, output_size)
    # else:
    #     input_y = torch.zeros(1, 1, output_size - num_trill_param)
    # input_y[0,0,0] = start_tempo
    # # input_y[0,0,1] = 1
    # # input_y[0,0,2] = 64

    #
    input_y[0,0,0] = start_tempo_norm
    for i in range(1, TOTAL_OUTPUT - 1):
        input_y[0, 0, i] -= means[1][i]
        input_y[0, 0, i] /= stds[1][i]
    input_y = input_y.to(DEVICE)
    tempo_stats = [means[1][0], stds[1][0]]

    initial_z = [args.latent] * NET_PARAM.encoder.size
    graph = edges_to_matrix(edges, batch_x.shape[1])
    prediction = perform_xml(batch_x, input_y, graph, note_locations, tempo_stats, initial_z=initial_z)

    # outputs = outputs.view(-1, num_output)
    prediction = np.squeeze(np.asarray(prediction))
    # prediction = outputs.cpu().detach().numpy()
    for i in range(15):
        prediction[:, i] *= stds[1][i]
        prediction[:, i] += means[1][i]
    # print(prediction)
    # print(means, stds)
    output_features = []
    # for i in range(100):
    #     pred = prediction[i]
    #     print(pred[0:4])
    num_notes = len(xml_notes)
    for i in range(num_notes):
        pred = prediction[i]
        # feat = {'IOI_ratio': pred[0], 'articulation': pred[1], 'loudness': pred[2], 'xml_deviation': 0,
        feat = xml_matching.MusicFeature()
        feat.qpm = pred[0]
        feat.velocity = pred[1]
        feat.xml_deviation = pred[2]
        feat.articulation = pred[3]
        # feat.xml_deviation = 0
        feat.pedal_refresh_time = pred[4]
        feat.pedal_cut_time = pred[5]
        feat.pedal_at_start = pred[6]
        feat.pedal_at_end = pred[7]
        feat.soft_pedal = pred[8]
        feat.pedal_refresh = pred[9]
        feat.pedal_cut = pred[10]

        feat.beat_index = note_locations[i].beat
        feat.measure_index = note_locations[i].measure

        feat.trill_param = pred[11:16]
        feat.trill_param[0] = round(feat.trill_param[0]).astype(int)
        feat.trill_param[1] = (feat.trill_param[1])
        feat.trill_param[2] = (feat.trill_param[2])
        feat.trill_param[3] = (feat.trill_param[3])
        feat.trill_param[4] = round(feat.trill_param[4])

        if test_x[i][is_trill_index_score] == 1:
            print(feat.trill_param)
        #
        # feat.passed_second = pred[0]
        # feat.duration_second = pred[1]
        # feat.pedal_refresh_time = pred[3]
        # feat.pedal_cut_time = pred[4]
        # feat.pedal_at_start = pred[5]
        # feat.pedal_at_end = pred[6]
        # feat.soft_pedal = pred[7]
        # feat.pedal_refresh = pred[8]
        # feat.pedal_cut = pred[9]

        # feat = {'qpm': pred[0], 'articulation': pred[1], 'loudness': pred[2], 'xml_deviation': pred[3],
        #         'pedal_at_start': pred[6], 'pedal_at_end': pred[7], 'soft_pedal': pred[8],
        #         'pedal_refresh_time': pred[4], 'pedal_cut_time': pred[5], 'pedal_refresh': pred[9],
        #         'pedal_cut': pred[10]}
        output_features.append(feat)
    num_notes = len(xml_notes)
    performanceWorm.plot_performance_worm(output_features, path_name + 'perfWorm.png')

    # output_xml = xml_matching.apply_perform_features(xml_notes, output_features)
    output_xml = xml_matching.apply_tempo_perform_features(xml_doc, xml_notes, output_features, start_time= 1, predicted=True)
    # output_xml = xml_matching.apply_time_position_features(xml_notes, output_features, start_time=1)

    output_midi = xml_matching.xml_notes_to_midi(output_xml)

    xml_matching.save_midi_notes_as_piano_midi(output_midi, path_name + 'performed_by_nn.mid', bool_pedal=args.boolPedal, disklavier=True)



elif args.sessMode=='plot':
    if os.path.isfile(args.resume):
        print("=> loading checkpoint '{}'".format(args.resume))
        checkpoint = torch.load(args.resume)
        # args.start_epoch = checkpoint['epoch']
        best_valid_loss = checkpoint['best_valid_loss']
        MODEL.load_state_dict(checkpoint['state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer'])
        print("=> loaded checkpoint '{}' (epoch {})"
              .format(args.resume, checkpoint['epoch']))
    else:
        print("=> no checkpoint found at '{}'".format(args.resume))


    with open(args.dataName + ".dat", "rb") as f:
        u = pickle._Unpickler(f)
        u.encoding = 'latin1'
        # p = u.load()
        # complete_xy = pickle.load(f)
        complete_xy = u.load()

    with open(args.dataName + "_stat.dat", "rb") as f:
        u = pickle._Unpickler(f)
        u.encoding = 'latin1'
        means, stds = u.load()

    perform_num = len(complete_xy)
    tempo_stats = [means[1][0], stds[1][0]]

    train_perf_num = int(perform_num * training_ratio)
    train_xy = complete_xy[:train_perf_num]
    test_xy = complete_xy[train_perf_num:]

    n_tuple = 0
    for xy_tuple in test_xy:
        n_tuple += 1
        train_x = xy_tuple[0]
        train_y = xy_tuple[1]
        prev_feature = xy_tuple[2]
        note_locations = xy_tuple[3]

        data_size = len(train_x)
        total_batch_num = int(math.ceil(data_size / (TIME_STEPS * batch_size)))
        batch_size=1
        for step in range(total_batch_num - 1):
            batch_start = step * batch_size * TIME_STEPS
            batch_end = (step + 1) * batch_size * TIME_STEPS
            batch_x = Variable(
                torch.Tensor(train_x[batch_start:batch_end]))
            batch_y = train_y[batch_start:batch_end]
            # print(batch_x.shape, batch_y.shape)
            # input_y = Variable(
            #     torch.Tensor(prev_feature[step * batch_size * time_steps:(step + 1) * batch_size * time_steps]))
            # input_y = torch.cat((zero_tensor, batch_y[0:batch_size * time_steps-1]), 0).view((batch_size, time_steps,num_output)).to(device)
            batch_x = batch_x.view((batch_size, TIME_STEPS, SCORE_INPUT)).to(DEVICE)
            # is_beat_batch = is_beat_list[batch_start:batch_end]
            # batch_y = batch_y.view((batch_size, time_steps, num_output)).to(device)
            # input_y = input_y.view((batch_size, time_steps, num_output)).to(device)

            # hidden = model.init_hidden(1)
            # final_hidden = model.init_final_layer(1)
            # outputs, hidden, final_hidden = model(batch_x, input_y, hidden, final_hidden)
            #
            if args.trainTrill:
                input_y = torch.zeros(1, 1, TOTAL_OUTPUT)
            else:
                input_y = torch.zeros(1, 1, TOTAL_OUTPUT - num_trill_param)

            input_y[0] = batch_y[0][0]
            input_y = input_y.view((1, 1, TOTAL_OUTPUT)).to(DEVICE)
            outputs = perform_xml(batch_x, input_y, note_locations, tempo_stats)
            outputs = torch.Tensor(outputs).view((1, -1, TOTAL_OUTPUT))

            outputs = outputs.cpu().detach().numpy()
            # batch_y = batch_y.cpu().detach().numpy()
            batch_y = np.asarray(batch_y).reshape((1, -1, TOTAL_OUTPUT))
            plt.figure(figsize=(10, 7))
            for i in range(4):
                plt.subplot(411+i)
                plt.plot(batch_y[0, :, i])
                plt.plot(outputs[0, :, i])
            plt.savefig('images/piece{:d},seg{:d}.png'.format(n_tuple, step))
            plt.close()