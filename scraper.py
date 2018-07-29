import pandas as pd
import numpy as np
import pprint
from sklearn.metrics import mean_squared_error
import spotipy.util as util
import spotipy.oauth2 as oauth2
import spotipy


from spotipy.oauth2 import SpotifyClientCredentials
cid ="b22cf494e54946d6a2a3e0ed65caa306"
secret = "e86002955042417a992518c25eb64e23"
playlistID = '5MXacL3fItt8eXXA2HREMi'

scope = 'playlist-read-private playlist-modify-private playlist-read-collaborative playlist-modify-public'
username = '126986257'
token = util.prompt_for_user_token(username,scope,client_id=cid,client_secret=secret,redirect_uri='https://localhost')
flowFactor = 4
rootIndex = 121
featuresMultiplier = 0.6
genresMultiplier = 1-featuresMultiplier
featuresAlpha = 0.25
genresAlpha = 0.25
createPlaylist = False

def ema(data, alpha):
    data = data[::-1]
    runningSum = np.zeros_like(data[0],dtype=np.float64)
    for index, vector in enumerate(data):
        if index == 0:
            runningSum += vector
        else:
            runningSum = vector*alpha + runningSum*(1.0-alpha)
    return runningSum

def songGenreMatrix(songToArtistMap):
    artistList = []
    for value in songToArtistMap.itervalues():
        for id in value:
            artistList.append(id)

    artistList = [str(r) for r in artistList]
    artistToGenreMap = {}
    GenreList = []
    for i in range(0, len(artistList),50):
        artists = sp.artists(artistList[i:i+50])
        for artist in artists['artists']:
            if artist['genres']:
                GenreList.append(artist['genres'])
                artistToGenreMap[artist['id']] = artist['genres']

    uniqueGenres = []
    for genreSet in GenreList:
        for genre in genreSet:
            if genre not in uniqueGenres:
                uniqueGenres.append(genre)

    uniqueGenres = [str(r) for r in uniqueGenres]

    songToGenreMatrix = np.zeros((len(songToArtistMap),len(uniqueGenres)),dtype=np.float64)
    for index, value in enumerate(songToArtistMap.items()):
        songToVector = np.zeros_like(songToGenreMatrix[0])
        for artist in value[1]:
            if artist in artistToGenreMap:
                for genre in artistToGenreMap[artist]:
                    # print genre
                    songToVector[uniqueGenres.index(genre)] += 1.0
        songToGenreMatrix[index] = songToVector

    data = pd.DataFrame(data=songToGenreMatrix)
    data.insert(0,"Song Name", songToArtistMap.keys())
    data.set_index("Song Name", inplace=True)

    return data

if token:
    sp = spotipy.Spotify(auth=token)
    sp.trace = False

    playlistName = sp.user_playlist(username,playlistID)['name']
    results = sp.user_playlist_tracks(username,playlistID)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    ids = []
    names = []
    songToArtistsList = {}

    for track in tracks:
        if (track['track']['id'] != None):
            ids.append(track['track']['id'])
            if (track['track']['name'] != None):
                names.append(track['track']['name'])
            if (track['track']['artists'] != None):
                temp = []
                for artist in track['track']['artists']:
                    if artist['id'] != None:
                        temp.append(artist['id'])
                songToArtistsList[track['track']['name']] = temp

    songToGenreMatrix = songGenreMatrix(songToArtistsList)

    features = []
    for i in range(0,len(tracks),50):
        audio_features = sp.audio_features(ids[i:i+50])
        for track in audio_features:
            if track != None:
                features.append(track)


    df = pd.DataFrame(features)
    featureList = list(df.columns)

    #0,2,4,6,8,10,11,12,13,17

    featureSet = []
    spotifyIDs = []

    for row in df.as_matrix():
        temp = [row[0],row[2],row[4],row[6],row[8],row[10],row[12],row[13],row[17]]
        spotifyID = row[16]
        featureSet.append(temp)
        spotifyIDs.append(spotifyID)

    featureSet = np.asarray(featureSet)
    for row in featureSet:
        row[6] /= np.max([featureSet[:,6]])
        row[7] /= np.max([featureSet[:,7]])

        for elem in range(len(row)):
            if row[elem] == 0.0:
                row[elem] += 0.0001
            if row[elem] == 1.0:
                row[elem] -= 0.0001

    optimizedTrackList = []
    optimizedTrackList.append(rootIndex)

    names = np.asarray(names)

    for index in range(len(featureSet)):
        minimum = 10000000
        minIndex = -1
        featuresAverage = np.zeros_like(featureSet[0])
        genresAverage = np.zeros_like(songToGenreMatrix[0])
        if (index == 0):
            featuresAverage = featureSet[optimizedTrackList[0]]
            genresAverage = songToGenreMatrix.loc[str(names[optimizedTrackList[0]])]
        elif (index > 0 and index < flowFactor):
            featuresAverage = ema(featureSet[optimizedTrackList[-index:]], featuresAlpha)
            genresAverage = ema(songToGenreMatrix.loc[names[optimizedTrackList[-index:]]].as_matrix(), genresAlpha)
        else:
            featuresAverage = ema(featureSet[optimizedTrackList[-flowFactor:]],featuresAlpha)
            genresAverage = ema(songToGenreMatrix.loc[names[optimizedTrackList[-flowFactor:]]].as_matrix(), genresAlpha)
        for indexCheck in range(len(featureSet)):
            featuresMSE = mean_squared_error(featuresAverage,featureSet[indexCheck])
            genresMSE = mean_squared_error(genresAverage, songToGenreMatrix.loc[names[indexCheck]].as_matrix())
            totalMSE = featuresMultiplier * featuresMSE + genresMultiplier * genresMSE
            if (totalMSE < minimum and indexCheck not in optimizedTrackList):
                minimum = totalMSE
                minIndex = indexCheck
        if (minIndex != -1):
            optimizedTrackList.append(minIndex)

    if (createPlaylist):
        playlistNew = sp.user_playlist_create(username,playlistName+" Optimized")
        newPlaylistId = playlistNew['uri']

        spotifyIDs = np.asarray(spotifyIDs)

        for i in range(0,len(optimizedTrackList),50):
            tracks = spotifyIDs[optimizedTrackList[i:i+50]]
            sp.user_playlist_add_tracks(username, newPlaylistId,tracks)
    for index in optimizedTrackList:
        print names[index]
else:
    print("Can't get token for", username)