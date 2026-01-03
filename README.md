# Demo

[![Watch the video](https://img.youtube.com/vi/21M1D2h5FdA/maxresdefault.jpg)](https://www.youtube.com/watch?v=21M1D2h5FdA)

# How to use

You must be using the Emulator mGBA. 

Start up mGBA and load your ROM. 

In mGBA open Tools > Scripting...

In the Scripting Window that opens, Open File > Load Script...

Navigate to the repo and select the server.lua file

(A note on this server is it will only ever accept one connection. 
You will need to select File > Reset in the scripting window and restart the server.lua script before attempting to reconnect)

If this is your first time running the client, you will need to do the following:
In the terminal you will need to create a virtual environment:

```bash
python3 -m venv ./
```
Enter the virtual environment: 

```bash
. bin/activate
```

Install the dependant packages: 

```bash
pip install -r requirements.txt
```

Once the environment has been setup you will need to run the following:
```
. bin/activate
python3 client.py
```

# Later improvements that can be made. 

## Making the overlay generic
This overlay will only work with Japanese Gold. 
The reason for this is that the address locations differ between games.
However the structure of the memory once you have located the correct base addresses should be identical. 
With how I have written this overlay it should be easy enough to update the base addresses for which ever of the 3 (I guess 6) games. 

I have also included a mem_find.py utility that should be very helpful in finding these values.

An example would be if you have Aipom and Alakazam in the first and second slots of your party you can look for BE 41 values in memory using `python3 mem_find.py BE41`

"Why didnt you do this?", you might ask. I have been working on this for over 10 days straight and I wish to do something else now.

## Adding maps for dungeons or implementing map specific behaviour 
I have also been able to find the map group and IDs. 
You could implement something to have a map load in the bottom right as you move from location to location. 
Could be useful for places like Mt. Mortar or Tin Tower. 

## Adding Timer, and or IGT display
There is a place in memory for the IGT it is just a matter of finding it and then decoding it. 

## Adding splits for timed runs 
I am already tracking pretty carefully the badges. adding splits would be a matter of combining a reading of the IGT and noting the time when a badge is given. 
