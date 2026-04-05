using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using System.Threading;
using Binary;
using Foundation;
using Licensing;

[assembly: CompilationRelaxations(8)]
[assembly: RuntimeCompatibility(WrapNonExceptionThrows = true)]
[assembly: Debuggable(DebuggableAttribute.DebuggingModes.IgnoreSymbolStoreSequencePoints)]
[assembly: AssemblyTitle("Hardware")]
[assembly: AssemblyDescription("")]
[assembly: AssemblyConfiguration("")]
[assembly: AssemblyCompany("")]
[assembly: AssemblyProduct("Hardware")]
[assembly: AssemblyCopyright("Copyright ©  2013")]
[assembly: AssemblyTrademark("")]
[assembly: ComVisible(false)]
[assembly: Guid("0d3fb7c2-80e7-424e-a33d-766d55fcd399")]
[assembly: AssemblyFileVersion("1.0.0.0")]
[assembly: TargetFramework(".NETFramework,Version=v4.0,Profile=Client", FrameworkDisplayName = ".NET Framework 4 Client Profile")]
[assembly: AssemblyVersion("1.0.0.0")]
namespace Hardware;

public class BitBangDevice : Device
{
	private const byte TXD = 1;

	private const byte RXD = 2;

	private const byte RTS = 4;

	private const byte CTS = 8;

	private const byte DTR = 16;

	private const byte DSR = 32;

	private const byte DCD = 64;

	private const byte RI = 128;

	private const uint BaseAverage = 11u;

	private readonly byte[] byteBuffer = new byte[32768];

	private readonly byte[] bitBuffer = new byte[32768];

	private readonly byte[] on = new byte[1] { 16 };

	private readonly byte[] off = new byte[1] { 20 };

	private ulong zeros;

	private ulong ones;

	private double signalQuality;

	private bool signalDropout;

	public double SignalQuality => Math.Min(Math.Max(0.0, signalQuality), 1.0);

	public override DeviceBits Bits
	{
		get
		{
			lock (bitBuffer)
			{
				return base.Bits;
			}
		}
	}

	private static void Main(string[] args)
	{
		Log.Open("Diode.log");
		Log.WriteLine("****************************** Diode test ******************************");
		int result = 32;
		if (args.Length != 0)
		{
			int.TryParse(args[0], out result);
		}
		Device[] array = Device.Get(DeviceImplementation.BitBang);
		Device[] array2 = array;
		for (int i = 0; i < array2.Length; i++)
		{
			BitBangDevice bitBangDevice = (BitBangDevice)array2[i];
			Console.WriteLine("Device #{0}: {1} {2} {3} {4} {5} {7:X8} {6}", bitBangDevice.index, bitBangDevice.usbPort, bitBangDevice.handle, bitBangDevice.type, bitBangDevice.mode, bitBangDevice.serialNumber, bitBangDevice.description, bitBangDevice.id);
		}
		using BitBangDevice bitBangDevice2 = (BitBangDevice)array[0];
		if (!bitBangDevice2.Open())
		{
			return;
		}
		byte[] array3 = new byte[32];
		int[] array4 = new int[256];
		DateTime now = DateTime.Now;
		bool flag = bitBangDevice2.BeginRead(quality: true);
		TimeSpan timeSpan = DateTime.Now - now;
		Console.WriteLine("Start {0} in {1} ms", flag ? "succeeded" : "failed", (int)timeSpan.TotalMilliseconds);
		now = DateTime.Now;
		StringBuilder stringBuilder = new StringBuilder(result * 128);
		int j;
		for (j = 0; j < result; j++)
		{
			if (!bitBangDevice2.ReadBytes(array3, 0, array3.Length))
			{
				break;
			}
			byte[] array5 = array3;
			foreach (byte b in array5)
			{
				array4[b]++;
				stringBuilder.AppendFormat("{0:X2} ", b);
			}
			stringBuilder.AppendLine();
		}
		bitBangDevice2.EndRead(quality: true);
		timeSpan = DateTime.Now - now;
		Console.WriteLine(stringBuilder);
		Console.WriteLine("\nRead {0} bytes ({1} lines) in {2} ms", j * array3.Length, j, (int)timeSpan.TotalMilliseconds);
		Console.WriteLine("\nDistribution:  0s: {0} / 1s: {1} Signal quality: {2:F1}%", bitBangDevice2.zeros, bitBangDevice2.ones, bitBangDevice2.SignalQuality * 100.0);
		for (int k = 0; k < array4.Length; k++)
		{
			Console.Write("{0} ", array4[k].ToString().PadLeft(5));
			if (k % 16 == 15)
			{
				Console.WriteLine();
			}
		}
	}

	private bool CheckSignalQuality()
	{
		if (zeros + ones >= (ulong)bitBuffer.Length)
		{
			double num = 1.0 - (double)((zeros > ones) ? (zeros - ones) : (ones - zeros)) / (double)(zeros + ones);
			zeros = (ones = 0uL);
			if (num < 0.002)
			{
				signalQuality = 0.0;
				Log.WriteLine("Signal quality {0:F1}%", signalQuality);
				return false;
			}
			signalQuality = 0.9 * signalQuality + 0.1 * num;
			Log.WriteLine("Signal quality {0:F1}%", SignalQuality * 100.0);
		}
		return true;
	}

	internal BitBangDevice()
	{
	}

	public override bool Open()
	{
		lock (bitBuffer)
		{
			if (!base.IsOpen)
			{
				if (Device.FT_OpenEx(new StringBuilder(serialNumber), OpenMode.SerialNumber, out var intPtr) != 0 || intPtr == IntPtr.Zero)
				{
					return false;
				}
				if (Device.FT_ResetPort(intPtr) != 0)
				{
					return false;
				}
				if (Device.FT_SetBaudRate(intPtr, 57600u) != 0)
				{
					return false;
				}
				handle = intPtr;
			}
			return base.IsOpen;
		}
	}

	public override bool BeginRead(bool quality)
	{
		lock (bitBuffer)
		{
			if (Device.FT_SetBitMode(handle, 52, BitMode.AsyncBitBang) != 0)
			{
				return false;
			}
			if (Device.FT_Write(handle, on, 1u, out var bytesWritten) != 0 || bytesWritten != 1)
			{
				return false;
			}
			if (Device.FT_Purge(handle, PurgeMode.ReceiveBuffer) != 0)
			{
				return false;
			}
			zeros = (ones = 0uL);
			signalDropout = false;
			double num = Math.Max(0.4, signalQuality - 0.2);
			double num2 = Math.Max(0.8, signalQuality);
			if (quality)
			{
				for (int i = 1; i <= 42; i++)
				{
					if (Device.FT_Read(handle, bitBuffer, (uint)bitBuffer.Length, out var bytesRead) != 0 || bytesRead != bitBuffer.Length)
					{
						return false;
					}
					byte[] array = bitBuffer;
					for (int j = 0; j < array.Length; j++)
					{
						if ((array[j] & 2u) != 0)
						{
							ones++;
						}
						else
						{
							zeros++;
						}
					}
					bool flag = CheckSignalQuality();
					if (signalQuality > num2 && flag)
					{
						return true;
					}
					if (i > 14 && signalQuality > num && flag)
					{
						return true;
					}
					if (i > 28 && flag)
					{
						return true;
					}
				}
				return false;
			}
			return true;
		}
	}

	public override void EndRead(bool quality)
	{
		lock (bitBuffer)
		{
			if (Device.FT_SetBitMode(handle, 55, BitMode.AsyncBitBang) == Result.Ok && Device.FT_Write(handle, off, 1u, out var _) == Result.Ok)
			{
				_ = 1;
			}
		}
	}

	public override bool ReadBits(byte[] buffer, int offset, int count, int average)
	{
		if (buffer == null)
		{
			throw new ArgumentNullException("buffer");
		}
		if (offset < 0 || offset > buffer.Length)
		{
			throw new ArgumentOutOfRangeException("offset");
		}
		if (count < 0 || offset + count > buffer.Length)
		{
			throw new ArgumentOutOfRangeException("count");
		}
		lock (bitBuffer)
		{
			uint num = ((average < 1) ? 11u : ((uint)(11 * average)));
			while (count > 0)
			{
				uint num2 = (uint)((count * num < bitBuffer.Length) ? (count * num) : bitBuffer.Length);
				num2 -= num2 % num;
				Device.FT_SetTimeouts(handle, 5000u, 0u);
				if (Device.FT_Read(handle, bitBuffer, num2, out var bytesRead) != 0 || bytesRead == 0 || bytesRead > num2)
				{
					return false;
				}
				for (uint num3 = 0u; num3 < bytesRead; num3++)
				{
					bool flag = (bitBuffer[num3] & 2) != 0;
					if (flag)
					{
						ones++;
					}
					else
					{
						zeros++;
					}
					bitBuffer[num3] = (byte)(flag ? 1u : 0u);
				}
				if (!CheckSignalQuality())
				{
					if (signalDropout)
					{
						return false;
					}
					signalDropout = true;
					Log.WriteLine("Diode off");
					if (Device.FT_Write(handle, off, 1u, out var bytesWritten) != 0 || bytesWritten != 1)
					{
						return false;
					}
					if (Device.FT_Write(handle, on, 1u, out bytesWritten) != 0 || bytesWritten != 1)
					{
						return false;
					}
					Log.WriteLine("Diode on");
					for (int i = 1; i <= 14; i++)
					{
						Device.FT_Read(handle, bitBuffer, (uint)bitBuffer.Length, out bytesRead);
					}
					Array.Clear(bitBuffer, 0, bitBuffer.Length);
					Log.WriteLine("Diode continue");
				}
				uint num4 = 0u;
				uint num5 = num;
				for (int j = 0; j < bytesRead; j++)
				{
					num4 += bitBuffer[j];
					if (num5 == 1)
					{
						bitBuffer[j / num] = (byte)((num4 * 2 > num) ? 1u : 0u);
						num4 = 0u;
						num5 = num;
					}
					else
					{
						num5--;
					}
				}
				bytesRead /= num;
				Array.Copy(bitBuffer, 0L, buffer, offset, bytesRead);
				count -= (int)bytesRead;
				offset += (int)bytesRead;
			}
			return true;
		}
	}

	public override bool ReadBytes(byte[] buffer, int offset, int count)
	{
		if (buffer == null)
		{
			throw new ArgumentNullException("buffer");
		}
		if (offset < 0 || offset > buffer.Length)
		{
			throw new ArgumentOutOfRangeException("offset");
		}
		if (count < 0 || offset + count > buffer.Length)
		{
			throw new ArgumentOutOfRangeException("count");
		}
		lock (byteBuffer)
		{
			while (count > 0)
			{
				int num = ((count * 8 < bitBuffer.Length) ? (count * 8) : bitBuffer.Length);
				if (!ReadBits(byteBuffer, 0, num, 1))
				{
					return false;
				}
				byte b = 0;
				byte b2 = 128;
				for (int i = 0; i < num; i++)
				{
					if (byteBuffer[i] != 0)
					{
						b |= b2;
					}
					if (b2 == 1)
					{
						byteBuffer[i / 8] = b;
						b = 0;
						b2 = 128;
					}
					else
					{
						b2 >>= 1;
					}
				}
				int num2 = num / 8;
				Array.Copy(byteBuffer, 0, buffer, offset, num2);
				count -= num2;
				offset += num2;
			}
			return true;
		}
	}

	public override void Reset()
	{
		lock (bitBuffer)
		{
			base.Reset();
		}
	}

	public override void Close()
	{
		if (base.IsOpen)
		{
			Device.FT_SetBitMode(handle, 0, BitMode.Reset);
		}
		base.Close();
	}
}
[Flags]
public enum DeviceBits : byte
{
	None = 0,
	Bit0 = 1,
	Bit1 = 2,
	Bit2 = 4,
	Bit3 = 8
}
public enum DeviceType : uint
{
	FT232B,
	FT232AM,
	FT100AX,
	Unknown,
	FT223C,
	FT232R,
	FT2232H,
	FT4232H,
	FT232H,
	FTXSeries
}
public enum DeviceImplementation
{
	UART,
	BitBang
}
public abstract class Device : IDisposable
{
	protected enum Result : uint
	{
		Ok,
		Invalid,
		NotFound,
		NotOpened,
		IOError,
		InsufficientResources,
		InvalidParameter,
		InvalidBaudRate
	}

	protected enum OpenMode : uint
	{
		SerialNumber = 1u,
		Description = 2u,
		Location = 4u
	}

	[Flags]
	protected enum DeviceMode : uint
	{
		None = 0u,
		Open = 1u,
		HiSpeed = 2u
	}

	protected enum WordLength : byte
	{
		SevenBits = 7,
		EightBits
	}

	protected enum StopBits : byte
	{
		One = 0,
		Two = 2
	}

	protected enum Parity : byte
	{
		None,
		Odd,
		Even,
		Mark,
		Space
	}

	protected enum FlowControl : ushort
	{
		None,
		RtsCts,
		DtrDsr,
		XonXoff
	}

	[Flags]
	protected enum PurgeMode : uint
	{
		None = 0u,
		ReceiveBuffer = 1u,
		TransmitBuffer = 2u
	}

	[Flags]
	protected enum BitMode : byte
	{
		Reset = 0,
		AsyncBitBang = 1,
		MPSSE = 2,
		SyncBitBang = 4,
		MCUHost = 8,
		FastSerial = 0x10,
		CBUSBitBang = 0x20,
		SyncFIFO = 0x40
	}

	[Flags]
	protected enum Status : uint
	{
		ClearToSend = 0x10u,
		DataSetReady = 0x20u,
		RingIndicator = 0x40u,
		DataCarrierDetect = 0x80u,
		OverrunError = 0x200u,
		ParityError = 0x400u,
		FramingError = 0x800u,
		BreakInterrupt = 0x1000u,
		Unknown = 0x6000u
	}

	[UnmanagedFunctionPointer(CallingConvention.StdCall)]
	protected delegate Result FTID_GetChipIDFromHandleDelegate(IntPtr handle, out uint chipId);

	protected const uint VIDPID = 67330049u;

	protected const string FTDI_DLL = "ftd2xx";

	protected const string KERNEL32_DLL = "kernel32";

	private static readonly bool uart;

	protected static FTID_GetChipIDFromHandleDelegate FTID_GetChipIDFromHandle;

	protected uint index;

	protected IntPtr handle;

	protected DeviceType type;

	protected DeviceMode mode;

	protected uint id;

	protected string serialNumber;

	protected string description;

	protected uint usbPort;

	public int Index => (int)index;

	public DeviceType Type => type;

	public bool IsHiSpeed => (mode & DeviceMode.HiSpeed) != 0;

	public int USBPort => (int)usbPort;

	public int Id => (int)id;

	public string SerialNumber => serialNumber;

	public string Description => description;

	public virtual DeviceBits Bits
	{
		get
		{
			if (FT_SetBitMode(handle, 0, BitMode.CBUSBitBang) != 0)
			{
				return DeviceBits.None;
			}
			if (FT_GetBitMode(handle, out var b) != 0)
			{
				return DeviceBits.None;
			}
			if (FT_SetBitMode(handle, 0, BitMode.Reset) != 0)
			{
				return DeviceBits.None;
			}
			return (DeviceBits)(b & 0xFu);
		}
	}

	public bool IsOpen => handle != IntPtr.Zero;

	static Device()
	{
		uart = Log.GetCondition("uart", @default: false);
		string name = (Environment.Is64BitProcess ? "FTChipID64.dll" : "FTChipID.dll");
		string path = Path.GetTempFileName();
		using (Stream stream = typeof(Device).Assembly.GetManifestResourceStream(typeof(Device), name))
		{
			using FileStream destination = File.OpenWrite(path);
			stream.CopyTo(destination);
		}
		IntPtr library = LoadLibrary(path);
		FTID_GetChipIDFromHandle = (FTID_GetChipIDFromHandleDelegate)Marshal.GetDelegateForFunctionPointer(GetProcAddress(library, "FTID_GetChipIDFromHandle"), typeof(FTID_GetChipIDFromHandleDelegate));
		AppDomain.CurrentDomain.ProcessExit += delegate
		{
			FreeLibrary(library);
			File.Delete(path);
		};
	}

	public static Device Get(string idOrSerialNumber)
	{
		Device[] array = Get((!uart) ? DeviceImplementation.BitBang : DeviceImplementation.UART);
		foreach (Device device in array)
		{
			if (device.id.ToString("X8") == idOrSerialNumber || (device.id == 0 && device.serialNumber == idOrSerialNumber))
			{
				return device;
			}
		}
		return null;
	}

	public static Device[] Get(DeviceImplementation implementation)
	{
		try
		{
			if (FT_CreateDeviceInfoList(out var numberOfDevices) == Result.Ok)
			{
				StringBuilder stringBuilder = new StringBuilder(16);
				StringBuilder stringBuilder2 = new StringBuilder(64);
				List<Device> list = new List<Device>((int)numberOfDevices);
				for (uint num = 0u; num < numberOfDevices; num++)
				{
					Device device = ((implementation == DeviceImplementation.BitBang) ? ((Device)new BitBangDevice()) : ((Device)new UARTDevice()));
					if (implementation != 0)
					{
						if (implementation != DeviceImplementation.BitBang)
						{
							continue;
						}
						device = new BitBangDevice();
					}
					else
					{
						device = new UARTDevice();
					}
					if (FT_GetDeviceInfoDetail(num, out device.mode, out device.type, out var num2, out device.usbPort, stringBuilder, stringBuilder2, out device.handle) != 0 || num2 != 67330049)
					{
						continue;
					}
					device.index = num;
					device.serialNumber = stringBuilder.ToString();
					device.description = stringBuilder2.ToString();
					if (device.type == DeviceType.FT232R)
					{
						bool num3 = device.handle == IntPtr.Zero;
						if (num3)
						{
							FT_Open(num, out device.handle);
						}
						if (device.handle != IntPtr.Zero)
						{
							FTID_GetChipIDFromHandle(device.handle, out device.id);
						}
						if (num3 && device.handle != IntPtr.Zero)
						{
							FT_Close(device.handle);
						}
					}
					device.handle = IntPtr.Zero;
					list.Add(device);
				}
				return list.ToArray();
			}
		}
		catch
		{
		}
		return null;
	}

	[DllImport("kernel32")]
	protected static extern IntPtr LoadLibrary(string dllToLoad);

	[DllImport("kernel32")]
	protected static extern IntPtr GetProcAddress(IntPtr hModule, string procedureName);

	[DllImport("kernel32")]
	protected static extern bool FreeLibrary(IntPtr hModule);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_CreateDeviceInfoList(out uint numberOfDevices);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_GetDeviceInfoDetail(uint index, out DeviceMode mode, out DeviceType type, out uint id, out uint locationId, StringBuilder serialNumber, StringBuilder description, out IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_GetDeviceInfo(IntPtr handle, out DeviceType type, out uint id, StringBuilder serialNumber, StringBuilder description, IntPtr dummy);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_Open(uint index, out IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_OpenEx(StringBuilder serialNumber, OpenMode mode, out IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_Close(IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_ResetDevice(IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_Read(IntPtr handle, byte[] buffer, uint byteToRead, out uint bytesRead);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_Write(IntPtr handle, byte[] buffer, uint byteToWrite, out uint bytesWritten);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_SetBaudRate(IntPtr handle, uint baudRate);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_SetDataCharacteristics(IntPtr handle, WordLength wordLength, StopBits stopBits, Parity parity);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_SetFlowControl(IntPtr handle, FlowControl flowControl, byte xon, byte xoff);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_SetDtr(IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_ClrDtr(IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_SetRts(IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_ClrRts(IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_SetTimeouts(IntPtr handle, uint readTimeout, uint writeTimeout);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_GetBitMode(IntPtr handle, out byte mode);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_SetBitMode(IntPtr handle, byte mask, BitMode mode);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_Purge(IntPtr handle, PurgeMode mode);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_GetStatus(IntPtr handle, out uint bytesInReceiveQueue, out uint bytesInTransmitQueue, out uint eventStatus);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_GetModemStatus(IntPtr handle, out Status modemStatus);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_CyclePort(IntPtr handle);

	[DllImport("ftd2xx", CallingConvention = CallingConvention.StdCall)]
	protected static extern Result FT_ResetPort(IntPtr handle);

	~Device()
	{
		Close();
	}

	void IDisposable.Dispose()
	{
		Close();
	}

	public abstract bool Open();

	public abstract bool BeginRead(bool quality);

	public abstract void EndRead(bool quality);

	public abstract bool ReadBits(byte[] buffer, int offset, int count, int average);

	public abstract bool ReadBytes(byte[] buffer, int offset, int count);

	public virtual void Reset()
	{
		if (Open())
		{
			FT_CyclePort(handle);
		}
		handle = IntPtr.Zero;
	}

	public virtual void Close()
	{
		if (IsOpen)
		{
			FT_Close(handle);
		}
		handle = IntPtr.Zero;
	}
}
public abstract class BasicDiode : Diode
{
	protected static readonly BinaryBuffer buffer = new BinaryBuffer(4096);

	private static Device device;

	private static int retries;

	protected Device Device
	{
		get
		{
			if (device == null)
			{
				device = Device.Get(License.Diode);
			}
			if (device != null)
			{
				retries = 0;
			}
			else
			{
				retries++;
				_ = 3;
			}
			if (device != null && device.Open())
			{
				return device;
			}
			End(DiodeOperation.Recover, DiodeState.Error, success: false);
			return device;
		}
	}

	public override bool Recover()
	{
		lock (buffer)
		{
			Device device = Device;
			if (device != null)
			{
				if (!Begin(DiodeOperation.Recover, DiodeState.Idle) || !device.ReadBytes(buffer.Buffer, 0, 1))
				{
					return End(DiodeOperation.Recover, DiodeState.Error, success: false);
				}
				return End(DiodeOperation.Recover, DiodeState.Idle, success: true);
			}
			return false;
		}
	}

	public override bool Send(TimeSpan duration, ref bool cancel)
	{
		if (duration < TimeSpan.Zero)
		{
			throw new ArgumentOutOfRangeException();
		}
		lock (buffer)
		{
			Device device = Device;
			if (device != null)
			{
				if (!Begin(DiodeOperation.Send, DiodeState.Sending) || !device.ReadBytes(buffer.Buffer, 0, 1))
				{
					return End(DiodeOperation.Send, DiodeState.Error, success: false);
				}
				DateTime dateTime = DateTime.Now + duration;
				while (DateTime.Now < dateTime)
				{
					if (cancel)
					{
						return End(DiodeOperation.Send, DiodeState.Idle, success: false);
					}
					if (!device.ReadBytes(buffer.Buffer, 0, buffer.Length / 4))
					{
						return End(DiodeOperation.Send, DiodeState.Error, success: false);
					}
				}
				return End(DiodeOperation.Send, DiodeState.Idle, success: true);
			}
			return false;
		}
	}

	protected bool Begin(DiodeOperation operation, DiodeState state)
	{
		bool result = device.BeginRead(operation == DiodeOperation.FirstScan || operation == DiodeOperation.SingleScan || operation == DiodeOperation.Recover || operation == DiodeOperation.Send);
		if (operation != DiodeOperation.Recover)
		{
			OnDiodeStateChanged(state);
		}
		return result;
	}

	protected bool End(DiodeOperation operation, DiodeState state, bool success)
	{
		if (state == DiodeState.Error)
		{
			if (device != null)
			{
				device.Close();
			}
			device = null;
		}
		else
		{
			device.EndRead(operation == DiodeOperation.LastScan || operation == DiodeOperation.SingleScan || operation == DiodeOperation.Recover);
		}
		OnDiodeStateChanged(state);
		return success;
	}
}
public class DistributionDiode : BasicDiode
{
	public override bool Scan(DiodeOperation operation, int[] data, int cycles, ref bool cancel)
	{
		if (data == null)
		{
			throw new ArgumentNullException();
		}
		if (cycles < 0)
		{
			throw new ArgumentOutOfRangeException();
		}
		lock (BasicDiode.buffer)
		{
			Device device = base.Device;
			if (device != null)
			{
				Begin(operation, DiodeState.Scanning);
				Array.Clear(data, 0, data.Length);
				int num = data.Length * 4 * cycles;
				while (num > 0)
				{
					if (cancel)
					{
						return End(operation, DiodeState.Idle, success: false);
					}
					int num2 = ((num > BasicDiode.buffer.Length) ? BasicDiode.buffer.Length : num);
					if (!device.ReadBytes(BasicDiode.buffer.Buffer, 0, num2))
					{
						return End(operation, DiodeState.Error, success: false);
					}
					BasicDiode.buffer.Index = 0;
					uint num3 = 0u;
					for (int i = 0; i < num2; i += 4)
					{
						num3 += BasicDiode.buffer.ReadUInt32();
						ulong num4 = (ulong)(num3 * data.Length);
						num4 >>= 32;
						data[num4]++;
					}
					num -= num2;
				}
				return End(operation, DiodeState.Idle, success: true);
			}
			return false;
		}
	}
}
public class RemainderDiode : BasicDiode
{
	public override bool Scan(DiodeOperation operation, int[] data, int cycles, ref bool cancel)
	{
		if (data == null)
		{
			throw new ArgumentNullException();
		}
		if (cycles < 0)
		{
			throw new ArgumentOutOfRangeException();
		}
		lock (BasicDiode.buffer)
		{
			Device device = base.Device;
			if (device != null)
			{
				Begin(operation, DiodeState.Scanning);
				Array.Clear(data, 0, data.Length);
				int num = data.Length * cycles;
				while (num > 0)
				{
					if (cancel)
					{
						return End(operation, DiodeState.Idle, success: false);
					}
					int num2 = (int)(Math.Log(data.Length, 2.0) / 8.0 * (double)num);
					num2 = Math.Min((num2 | 3) + 5, BasicDiode.buffer.Length);
					if (!device.ReadBytes(BasicDiode.buffer.Buffer, 0, num2))
					{
						return End(operation, DiodeState.Error, success: false);
					}
					BasicDiode.buffer.Index = 0;
					int num3 = 0;
					ulong num4 = BasicDiode.buffer.ReadUInt32();
					for (int i = 4; i < num2; i += 4)
					{
						num4 ^= (ulong)BasicDiode.buffer.ReadUInt32() << 32;
						for (ulong num5 = 1uL; num5 <= uint.MaxValue; num5 *= (ulong)data.Length)
						{
							num3 += (int)(num4 / num5 % (ulong)data.Length);
							data[num3 % data.Length]++;
							if (--num == 0)
							{
								break;
							}
						}
						if (num == 0)
						{
							break;
						}
						num4 >>= 32;
					}
				}
				return End(operation, DiodeState.Idle, success: true);
			}
			return false;
		}
	}
}
public class QUANTEC6Diode : BasicDiode
{
	public override bool Scan(DiodeOperation operation, int[] data, int cycles, ref bool cancel)
	{
		if (data == null)
		{
			throw new ArgumentNullException();
		}
		if (cycles < 0)
		{
			throw new ArgumentOutOfRangeException();
		}
		lock (BasicDiode.buffer)
		{
			Device device = base.Device;
			if (device != null)
			{
				Begin(operation, DiodeState.Scanning);
				Array.Clear(data, 0, data.Length);
				int i;
				for (i = 1; i < 32 && (int)(1L << i) < data.Length; i++)
				{
				}
				int num = (i + 7) / 8;
				int num2 = data.Length * cycles;
				byte b = 0;
				int num3 = 0;
				bool flag = true;
				int num4 = 0;
				while (num2 > 0)
				{
					if (cancel)
					{
						return End(operation, DiodeState.Idle, success: false);
					}
					int num5 = ((num2 * num > BasicDiode.buffer.Length) ? BasicDiode.buffer.Length : (num2 * num));
					if (!device.ReadBytes(BasicDiode.buffer.Buffer, 0, num5))
					{
						return End(operation, DiodeState.Error, success: false);
					}
					BasicDiode.buffer.Index = 0;
					if (flag)
					{
						b = BasicDiode.buffer.ReadUInt8();
						num3 = 8;
						flag = false;
					}
					while (num5 - BasicDiode.buffer.Index >= num)
					{
						int num6 = 0;
						int num7 = i;
						if (num7 > 0)
						{
							int num8 = ((num7 < num3) ? num7 : num3);
							num6 = b;
							if (num8 < 8)
							{
								num6 >>= num3 - num8;
								num6 &= (1 << num8) - 1;
							}
							num7 -= num8;
							num3 -= num8;
						}
						if (num3 <= 0)
						{
							b = BasicDiode.buffer.ReadUInt8();
							num3 = 8;
						}
						while (num7 >= 8)
						{
							num6 <<= 8;
							num6 |= b;
							num7 -= 8;
							b = BasicDiode.buffer.ReadUInt8();
							num3 = 8;
						}
						if (num7 > 0)
						{
							num6 <<= num7;
							num6 |= b >> 8 - num7;
							num3 -= num7;
						}
						num6 += num4;
						num6++;
						num6 %= data.Length;
						if (num6 >= 0 && num6 < data.Length)
						{
							data[num6]++;
						}
						num4 = num6;
						if (--num2 == 0)
						{
							break;
						}
					}
				}
				return End(operation, DiodeState.Idle, success: true);
			}
			return false;
		}
	}
}
public class QUANTEC6DiodeWithRandom : BasicDiode
{
	public override bool Scan(DiodeOperation operation, int[] data, int cycles, ref bool cancel)
	{
		if (data == null)
		{
			throw new ArgumentNullException();
		}
		if (cycles < 0)
		{
			throw new ArgumentOutOfRangeException();
		}
		lock (BasicDiode.buffer)
		{
			Device device = base.Device;
			if (device != null)
			{
				Begin(operation, DiodeState.Scanning);
				Array.Clear(data, 0, data.Length);
				int i;
				for (i = 1; i < 32 && (int)(1L << i) < data.Length; i++)
				{
				}
				int num = (i + 7) / 8;
				int num2 = data.Length * cycles;
				byte b = 0;
				int num3 = 0;
				bool flag = true;
				Random random = new Random();
				while (num2 > 0)
				{
					if (cancel)
					{
						return End(operation, DiodeState.Idle, success: false);
					}
					int num4 = ((num2 * num > BasicDiode.buffer.Length) ? BasicDiode.buffer.Length : (num2 * num));
					if (!device.ReadBytes(BasicDiode.buffer.Buffer, 0, num4))
					{
						return End(operation, DiodeState.Error, success: false);
					}
					BasicDiode.buffer.Index = 0;
					if (flag)
					{
						b = BasicDiode.buffer.ReadUInt8();
						num3 = 8;
						flag = false;
					}
					while (num4 - BasicDiode.buffer.Index >= num)
					{
						int num5 = 0;
						int num6 = i;
						if (num6 > 0)
						{
							int num7 = ((num6 < num3) ? num6 : num3);
							num5 = b;
							if (num7 < 8)
							{
								num5 >>= num3 - num7;
								num5 &= (1 << num7) - 1;
							}
							num6 -= num7;
							num3 -= num7;
						}
						if (num3 <= 0)
						{
							b = BasicDiode.buffer.ReadUInt8();
							num3 = 8;
						}
						while (num6 >= 8)
						{
							num5 <<= 8;
							num5 |= b;
							num6 -= 8;
							b = BasicDiode.buffer.ReadUInt8();
							num3 = 8;
							if (--num2 == 0)
							{
								break;
							}
						}
						if (num2 > 0)
						{
							if (num6 > 0)
							{
								num5 <<= num6;
								num5 |= b >> 8 - num6;
								num3 -= num6;
							}
							num5 += random.Next();
							num5 %= data.Length;
							if (num5 >= 0 && num5 < data.Length)
							{
								data[num5]++;
							}
						}
						if (--num2 == 0)
						{
							break;
						}
					}
				}
				return End(operation, DiodeState.Idle, success: true);
			}
			return false;
		}
	}
}
public class SelectionDiode : BasicDiode
{
	public override bool Scan(DiodeOperation operation, int[] data, int cycles, ref bool cancel)
	{
		if (data == null)
		{
			throw new ArgumentNullException();
		}
		if (cycles < 0)
		{
			throw new ArgumentOutOfRangeException();
		}
		lock (BasicDiode.buffer)
		{
			Device device = base.Device;
			if (device != null)
			{
				Begin(operation, DiodeState.Scanning);
				Array.Clear(data, 0, data.Length);
				int average = 1 + (int)Math.Log(data.Length, 2.0);
				int num = data.Length * cycles;
				int num2 = 0;
				double num3 = 0.0;
				double num4 = 0.0;
				while (num > 0)
				{
					if (cancel)
					{
						return End(operation, DiodeState.Idle, success: false);
					}
					int num5 = ((num > BasicDiode.buffer.Length) ? BasicDiode.buffer.Length : num);
					if (!device.ReadBits(BasicDiode.buffer.Buffer, 0, num5, average))
					{
						return End(operation, DiodeState.Error, success: false);
					}
					for (int i = 0; i < num5; i++)
					{
						if (num2 >= data.Length)
						{
							num2 = 0;
						}
						bool num6 = BasicDiode.buffer.Buffer[i] != 0;
						if (num6)
						{
							data[num2]++;
						}
						if (num6)
						{
							num4 += 1.0;
						}
						else
						{
							num3 += 1.0;
						}
						num2++;
					}
					num -= num5;
				}
				bool result = End(operation, DiodeState.Idle, success: true);
				for (int j = 0; j < data.Length; j++)
				{
					data[j] = (int)((double)data[j] / (num4 / (num3 + num4)));
				}
				return result;
			}
			return false;
		}
	}
}
public enum DiodeOperation
{
	SingleScan,
	FirstScan,
	InBetweenScan,
	LastScan,
	Send,
	Recover
}
public enum DiodeType
{
	QUANTEC6 = 0,
	QUANTEC6WithRandom = 1,
	Remainder = 2,
	Distribution = 3,
	Selection = 4,
	Default = 1
}
public enum DiodeState
{
	Idle = 0,
	Scanning = 1,
	Sending = 2,
	Error = -1
}
public delegate void DiodeStateHandler(DiodeState state);
public abstract class Diode : IDisposable
{
	private static readonly Queue<Diode> queue;

	private static readonly ManualResetEvent queueChanged;

	private static Error m_cLog;

	private bool m_bCancel;

	public static Error ErrorLog => m_cLog;

	public static event DiodeStateHandler DiodeStateChanged;

	static Diode()
	{
		queue = new Queue<Diode>();
		queueChanged = new ManualResetEvent(initialState: false);
		m_cLog = new Error("Diode", bShowMessageBox: true);
		Thread thread = new Thread(Run);
		thread.Name = "DiodeWarmUp";
		thread.Priority = ThreadPriority.BelowNormal;
		thread.IsBackground = true;
		thread.Start();
	}

	private bool IsCancel()
	{
		return m_bCancel;
	}

	public static Diode Create(DiodeType type, ManualResetEvent cCancel = null)
	{
		Diode diode = type switch
		{
			DiodeType.QUANTEC6WithRandom => new QUANTEC6DiodeWithRandom(), 
			DiodeType.Remainder => new RemainderDiode(), 
			DiodeType.Distribution => new DistributionDiode(), 
			DiodeType.Selection => new SelectionDiode(), 
			_ => new QUANTEC6Diode(), 
		};
		if (Thread.CurrentThread.GetApartmentState() == ApartmentState.STA && !Thread.CurrentThread.IsBackground && !Thread.CurrentThread.IsThreadPoolThread)
		{
			ErrorLog.WriteErrorMessage(Error.ErrorTypes.Warning, "***DIODE IS USED FROM MAIN-THREAD");
			return diode;
		}
		lock (queue)
		{
			queue.Enqueue(diode);
			queueChanged.Set();
		}
		while (true)
		{
			lock (queue)
			{
				if (queue.Count == 0 || queue.Peek() == diode)
				{
					break;
				}
				if (queue.Count > 0 && queue.Peek().IsCancel())
				{
					queue.Dequeue();
					queueChanged.Set();
				}
				goto IL_0116;
			}
			IL_0116:
			if (cCancel != null)
			{
				int num = WaitHandle.WaitAny(new WaitHandle[2] { queueChanged, cCancel });
				if (num == 0)
				{
					queueChanged.Reset();
				}
				if (num == 1)
				{
					diode.m_bCancel = true;
					break;
				}
			}
			else
			{
				WaitHandle.WaitAny(new WaitHandle[1] { queueChanged });
				queueChanged.Reset();
			}
		}
		return diode;
	}

	~Diode()
	{
		Dispose();
	}

	public void Dispose()
	{
		lock (queue)
		{
			if (queue.Count > 0)
			{
				if (queue.Peek() == this)
				{
					queue.Dequeue();
				}
				else if (queue.Peek().IsCancel())
				{
					queue.Dequeue();
				}
			}
			queueChanged.Set();
		}
	}

	public static int GetMaximum(int[] data)
	{
		if (data == null)
		{
			throw new ArgumentNullException();
		}
		int num = int.MinValue;
		int result = -1;
		for (int i = 0; i < data.Length; i++)
		{
			if (num < data[i])
			{
				num = data[i];
				result = i;
			}
		}
		return result;
	}

	public abstract bool Recover();

	public abstract bool Send(TimeSpan duration, ref bool cancel);

	public abstract bool Scan(DiodeOperation operation, int[] data, int cycles, ref bool cancel);

	public int Scan(int range, int cycles, ref bool cancel)
	{
		if (range < 0)
		{
			throw new ArgumentOutOfRangeException();
		}
		int[] data = new int[range];
		if (!Scan(DiodeOperation.SingleScan, data, cycles, ref cancel))
		{
			return -1;
		}
		return GetMaximum(data);
	}

	protected virtual void OnDiodeStateChanged(DiodeState state)
	{
		if (state == DiodeState.Error)
		{
			Log.WriteLine("Diode error");
		}
		if (Diode.DiodeStateChanged != null)
		{
			Diode.DiodeStateChanged(state);
		}
	}

	private static void Run()
	{
		while (true)
		{
			try
			{
				Thread.Sleep(5000);
				using Diode diode = Create(DiodeType.QUANTEC6WithRandom);
				diode.Recover();
			}
			catch
			{
			}
		}
	}
}
public class UARTDevice : Device
{
	private static readonly bool rts = Log.GetCondition("rts", @default: true);

	private readonly byte[] buffer = new byte[4096];

	public override DeviceBits Bits
	{
		get
		{
			lock (buffer)
			{
				return base.Bits;
			}
		}
	}

	private int BytesAvailable
	{
		get
		{
			lock (buffer)
			{
				if (Device.FT_GetStatus(handle, out var bytesInReceiveQueue, out var _, out var _) != 0)
				{
					return 0;
				}
				return (int)bytesInReceiveQueue;
			}
		}
	}

	private static void Main(string[] args)
	{
		int result = 32;
		if (args.Length != 0)
		{
			int.TryParse(args[0], out result);
		}
		Device[] array = Device.Get(DeviceImplementation.UART);
		Device[] array2 = array;
		for (int i = 0; i < array2.Length; i++)
		{
			UARTDevice uARTDevice = (UARTDevice)array2[i];
			Console.WriteLine("Device #{0}: {1} {2} {3} {4} {5} {7:X8} {6}", uARTDevice.index, uARTDevice.usbPort, uARTDevice.handle, uARTDevice.type, uARTDevice.mode, uARTDevice.serialNumber, uARTDevice.description, uARTDevice.id);
		}
		using UARTDevice uARTDevice2 = (UARTDevice)array[0];
		if (!uARTDevice2.Open())
		{
			return;
		}
		DateTime now = DateTime.Now;
		byte[] array3 = new byte[32];
		int[] array4 = new int[256];
		for (int j = 0; j < result; j++)
		{
			uARTDevice2.ReadBytes(array3, 0, array3.Length);
			byte[] array5 = array3;
			foreach (byte b in array5)
			{
				array4[b]++;
				Console.Write("{0:X2} ", b);
			}
			Console.WriteLine("[{0}] {1}", uARTDevice2.BytesAvailable.ToString().PadLeft(4), uARTDevice2.Bits);
		}
		TimeSpan timeSpan = DateTime.Now - now;
		Console.WriteLine("\nRead {0} bytes in {1} ms", result * array3.Length, (int)timeSpan.TotalMilliseconds);
		Console.WriteLine("\nDistribution:");
		for (int k = 0; k < array4.Length; k++)
		{
			Console.Write("{0} ", array4[k].ToString().PadLeft(5));
			if (k % 16 == 15)
			{
				Console.WriteLine();
			}
		}
	}

	internal UARTDevice()
	{
	}

	public override bool Open()
	{
		lock (buffer)
		{
			if (!base.IsOpen)
			{
				if (Device.FT_OpenEx(new StringBuilder(serialNumber), OpenMode.SerialNumber, out var intPtr) != 0 || intPtr == IntPtr.Zero)
				{
					return false;
				}
				if (Device.FT_ResetPort(intPtr) != 0)
				{
					return false;
				}
				if (Device.FT_SetBitMode(intPtr, 0, BitMode.Reset) != 0)
				{
					return false;
				}
				if (Device.FT_SetBaudRate(intPtr, 115200u) != 0)
				{
					return false;
				}
				if (Device.FT_SetDataCharacteristics(intPtr, WordLength.EightBits, StopBits.One, Parity.None) != 0)
				{
					return false;
				}
				if (Device.FT_SetTimeouts(intPtr, 1500u, 1500u) != 0)
				{
					return false;
				}
				if (Device.FT_SetFlowControl(intPtr, FlowControl.None, 0, 0) != 0)
				{
					return false;
				}
				if (rts)
				{
					if (Device.FT_ClrDtr(intPtr) != 0)
					{
						return false;
					}
					if (Device.FT_ClrRts(intPtr) != 0)
					{
						return false;
					}
				}
				else
				{
					if (Device.FT_SetDtr(intPtr) != 0)
					{
						return false;
					}
					if (Device.FT_SetRts(intPtr) != 0)
					{
						return false;
					}
				}
				handle = intPtr;
			}
			return base.IsOpen;
		}
	}

	public override bool BeginRead(bool quality)
	{
		Flush();
		return base.IsOpen;
	}

	public override void EndRead(bool quality)
	{
		if (quality)
		{
			Flush();
		}
	}

	private void Flush()
	{
		lock (buffer)
		{
			uint bytesRead = 0u;
			if (Device.FT_GetStatus(handle, out var bytesInReceiveQueue, out var _, out var _) == Result.Ok && bytesInReceiveQueue != 0)
			{
				Device.FT_Read(handle, buffer, (bytesInReceiveQueue < buffer.Length) ? bytesInReceiveQueue : ((uint)buffer.Length), out bytesRead);
			}
		}
	}

	public override bool ReadBytes(byte[] buffer, int offset, int count)
	{
		lock (this.buffer)
		{
			if (buffer == null)
			{
				throw new ArgumentNullException("buffer");
			}
			if (offset < 0 || offset > buffer.Length)
			{
				throw new ArgumentOutOfRangeException("offset");
			}
			if (count < 0 || offset + count > buffer.Length)
			{
				throw new ArgumentOutOfRangeException("count");
			}
			if (count > 0)
			{
				if (rts && Device.FT_SetRts(handle) != 0)
				{
					return false;
				}
				if (!rts && Device.FT_ClrDtr(handle) != 0)
				{
					return false;
				}
				while (count > 0)
				{
					if (Device.FT_Read(handle, this.buffer, (uint)((count < this.buffer.Length) ? count : this.buffer.Length), out var bytesRead) != 0 || bytesRead == 0)
					{
						return false;
					}
					Array.Copy(this.buffer, 0L, buffer, offset, bytesRead);
					count -= (int)bytesRead;
					offset += (int)bytesRead;
				}
				if (rts && Device.FT_ClrRts(handle) != 0)
				{
					return false;
				}
				if (!rts && Device.FT_SetDtr(handle) != 0)
				{
					return false;
				}
			}
			return true;
		}
	}

	public override bool ReadBits(byte[] buffer, int offset, int count, int average)
	{
		return ReadBytes(buffer, offset, count);
	}

	public override void Reset()
	{
		lock (buffer)
		{
			base.Reset();
		}
	}

	public override void Close()
	{
		lock (buffer)
		{
			base.Close();
		}
	}
}
