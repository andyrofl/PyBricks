#!/usr/bin/env pybricks-micropython
#imports
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor
from pybricks.parameters import Port, Stop
from pybricks.tools import wait, StopWatch, DataLog
from pybricks.robotics import DriveBase
from pybricks.nxtdevices import LightSensor
from pybricks.parameters import Port
import DuckEyes


#CONSTANTS
BLOCKS_TO_MM = 300.2 #25.4MM * 13 INCHES
TRACKING_OUTSIDE = False
TRACKING_INSIDE = True

#TUNEABLES
WHEEL_DIAMETER = 41 #42.86
AXLE_TRACK = 108 #5 inches end to end, 3.25 inside edges
STRAIGHT_SPEED = 80
STRAIGHT_ACCELERATION = 55
TURN_RATE = 100
TURN_ACCELERATION = 25
TURN_MULTIPLIER = 1.2
TURN_SPEED_LIMIT = 9
BUMP_DISTANCE = 0.5
TURN_LAKE_LIMITER = -8

#variables and objects --initialization
brick = EV3Brick()
left = Motor(Port.B)
right = Motor(Port.A)
driver = DriveBase(left, right, WHEEL_DIAMETER, AXLE_TRACK)
driver.settings(STRAIGHT_SPEED, STRAIGHT_ACCELERATION, TURN_RATE, TURN_ACCELERATION)
global y_coordinate
global x_coordinate

def convert_blocks_to_MM(blocks):
	return blocks * BLOCKS_TO_MM 

'''
	calibrates high and low levels for each IR sensor to calculate an accurate midpoint given current light conditions
'''
def calibrate_sensors():
	distance = convert_blocks_to_MM(0.5)
	left_min = 85
	left_max = 8
	right_min = 85
	right_max = 8
	driver.drive(STRAIGHT_SPEED, 0)
	while(driver.distance()<distance):
		level_left = DuckEyes.get_left_level()
		level_right = DuckEyes.get_right_level()
		if(level_left < left_min):
			left_min= level_left
		if(level_left > left_max):
			left_max = level_left
		if(level_right < right_min):
			right_min = level_right
		if(level_right > right_max):
			right_max = level_right
	driver.stop()
	wait(300)
	driver.straight(-distance)
	DuckEyes.initialize_IR_levels(left_min, left_max, right_min, right_max)

'''
	function moves robot forward a specified number of "blocks" accounting for the need to come up a little short if we are making an interior turn.
	Navigation data in each Gizmoduck loop will handle changing the tracking edge
'''
def move_forward_by_blocks(number_of_blocks, tracking_edge, angle_rotation, start_inside, tracking_lake):
	tracking_sensor = DuckEyes.get_tracking_sensor(tracking_edge)
	counting_sensor = DuckEyes.get_counting_sensor(tracking_edge)
	midpoint_tracking = DuckEyes.get_IR_midpoint(tracking_sensor)
	swapped_tracking = DuckEyes.is_sensor_swapped(tracking_sensor, angle_rotation)
	crossed_final = False
	last_count_distance = 0
	is_about_to_exit = False
	lines_crossed = 0
	turn_rate = 0
	#if the previous turn was an outside turn, start in motion 
	if(not start_inside):
		print('bump')
		driver.drive(STRAIGHT_SPEED,0)
		wait(600)
	print('midpoint: ', midpoint_tracking, 'and lines: ', number_of_blocks)
	exit_condition = False
	while not exit_condition :
		driver.drive(STRAIGHT_SPEED, turn_rate)
		turn_rate =0
		#line counting and halting logic
		if(is_about_to_exit):
			if(driver.distance() > last_count_distance + convert_blocks_to_MM(BUMP_DISTANCE)):
				print('entered possible break point: ',driver.distance(), last_count_distance)
				print('break')
				#driver.straight(convert_blocks_to_MM(BUMP_DISTANCE))
				exit_condition = True
		if(counting_sensor.reflection() < 20):
			if(driver.distance() > (last_count_distance + 100)):
				last_count_distance = driver.distance()
				lines_crossed+=1
				print('crossed a line')
				#increment_coordinates(driver.angle())
				if(lines_crossed >= number_of_blocks):
					crossed_final = True
					is_about_to_exit = True
					#here
					print('is about to exit and crossed final')
				elif(lines_crossed == (number_of_blocks-1)):
					if(is_turn_inside(tracking_edge, angle_rotation)): #if the inside_outside returned false just cut the last block short
						is_about_to_exit = True
						print('is about to exit')
		else:#turn rate logic
			turn_rate = ((tracking_sensor.reflection() - midpoint_tracking)*TURN_MULTIPLIER*tracking_edge)
			if(lines_crossed == 0 and (turn_rate*tracking_edge)>TURN_SPEED_LIMIT):
				turn_rate =(turn_rate/abs(turn_rate))*TURN_SPEED_LIMIT #if the turn rate towards the target in the first block is too sharp, limit it. turns awy from the line are uncapped.
			if(tracking_lake and turn_rate<TURN_LAKE_LIMITER):
				turn_rate = TURN_LAKE_LIMITER #if the turn rate is a value of lower than the limiter (a negative number for turning away) limit the turn rate
		#if(lines_crossed < number_of_blocks):

	driver.stop()
	return (crossed_final and not swapped_tracking) or (not crossed_final and swapped_tracking)

'''
	input distance_blocks represents the distance to move in "blocks" but may not be a whole number
	returns False as this function is only called during manual movement and does not need any line based compensation
'''
def move_forward_unchecked(distance_blocks):
	driver.straight(convert_blocks_to_MM(distance_blocks))
	return False
'''
	input angle_rotation specifies the number of degrees to rotate.
	a positive value rotates clockwise and a negative value rotates counter-clockwise
	there is currently no confirmation or compensation for this function outside of the next line follow operation.
'''
def rotate_degrees(angle_rotation):
	driver.turn(angle_rotation)

'''
	input: tracking_edge corresponding to a constant in Navigation. right edge is positive, left is negative, and 0 goes off grid
	input: angle_rotation where a positive sign indicates a right turn and negative indicates a left turn
	if the signs of both input values are the same return that robot is on the outside of the turn, if signs are different we are tracking inside, a value of zero should be handled elsewhere
'''
def is_turn_inside(tracking_edge, angle_rotation):
	if(tracking_edge*angle_rotation > 0):
		return TRACKING_OUTSIDE
	elif(tracking_edge*angle_rotation < 0):
		return TRACKING_INSIDE
	else:
		print('error logged in calculate_inside_outside function, returned ')
		return True
'''
	input: angle_rotation, the absolute heading of the DriveBase object
	function modifies either the X or Y coordinate in accordance with the input angle_rotation with the assumption that robot will generally align with one of four cardinal directions
'''
def increment_coordinates(angle_rotation):
	global y_coordinate
	global x_coordinate
	#modulus to round, then cases to incement x or y + or - depending on cardinal direction
	variance = angle_rotation % 90
	if(variance < 35):
		angle_rotation = (angle_rotation % 360) -variance
	elif(variance > 55):
		angle_rotation = (angle_rotation % 360) +(90-variance)
	
	if angle_rotation ==  0:
		y_coordinate -=1
	elif angle_rotation == 90:
		x_coordinate +=1
	elif angle_rotation == 180:
		y_coordinate +=1
	elif angle_rotation == 270:
		x_coordinate -=1
	else:
		print('coordinate increment out of bounds')

'''
	sets the global x coordinate
'''
#def set_x_coordinate(x_initial):
#global x_coordinate
#	x_coordinate = x_initial
#
'''
	sets the global y coordinate
'''
#def set_y_coordinate(y_initial):
#	global y_coordinate
#	y_coordinate = y_initial