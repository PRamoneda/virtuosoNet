SCORE_INPUT = 78 #score information only
DROP_OUT = 0.2
TOTAL_OUTPUT = 16

NUM_PRIME_PARAM = 11
NUM_TEMPO_PARAM = 1
VEL_PARAM_IDX = 1
DEV_PARAM_IDX = 2
PEDAL_PARAM_IDX = 3
num_second_param = 0
num_trill_param = 5
num_voice_feed_param = 0 # velocity, onset deviation
num_tempo_info = 0
num_dynamic_info = 0 # distance from marking, dynamics vector 4, mean_piano, forte marking and velocity = 4
is_trill_index_score = -11
is_trill_index_concated = -11 - (NUM_PRIME_PARAM + num_second_param)


MEAS_TEMPO_IDX = 13
BEAT_TEMPO_IDX = 11

# test_piece_list = [('schumann', 'Schumann'),
#                 ('mozart545-1', 'Mozart'),
#                 ('chopin_nocturne', 'Chopin'),
#                 ('chopin_fantasie_impromptu', 'Chopin'),
#                 ('cho_waltz_69_2', 'Chopin'),
#                 ('lacampanella', 'Liszt'),
#                 ('bohemian_rhapsody', 'Liszt')
#                 ]

test_piece_list = [
                ('bps_5_1', 'Beethoven'),
                ('bps_27_1', 'Beethoven'),
                ('bps_7_2', 'Beethoven'),
                ('bps_31_2', 'Beethoven'),
                ('bwv_858', 'Bach'),
                ('bwv_891', 'Bach'),
                ('schubert_ps', 'Schubert'),
                ('schubert_impromptu', 'Schubert'),
                ('mozart545-1', 'Mozart'),
                ('mozart_symphony', 'Mozart'),
                ('liszt_pag', 'Liszt'),
                ('chopin_etude_10_2', 'Chopin'),
                ('chopin_waltz_69_2', 'Chopin'),
                ('chopin_nocturne', 'Chopin'),
                ('chopin_noc_9_1', 'Chopin'),
                ('chopin_prelude_1', 'Chopin'),
                ('chopin_prelude_4', 'Chopin'),
                ('chopin_prelude_5', 'Chopin'),
                ('chopin_prelude_6', 'Chopin'),
                ('chopin_prelude_8', 'Chopin'),
                ('chopin_prelude_15', 'Chopin'),
                ('kiss_the_rain', 'Chopin'),
                ('bohemian_rhapsody', 'Liszt'),
                ('chopin_nocturne', 'Chopin'),
                ('chopin_fantasie_impromptu', 'Chopin'),
                ('schumann', 'Schumann'),
                   ]

emotion_folder_path = 'test_pieces/emotionNet/'
emotion_key_list = ['OR', 'Anger', 'Enjoy', 'Relax', 'Sad']
emotion_data_path  = [('Bach_Prelude_1', 'Bach', 1),
                      ('Clementi_op.36-1_mov3', 'Haydn', 3),
                      ('Kuhlau_op.20-1_mov1', 'Haydn', 2),
                      ]